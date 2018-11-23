#
# Bridge between the Onkyo AVR EISCP remote control protocol and MQTT.
# Allows to remotely control networked Onkyo AVRs and get status
# information.
#
# Written and (C) 2015-16 by Oliver Wagner <owagner@tellerulam.com>
# Portions copyright 2018 by Jeff Licquia <jeff@licquia.org>
# Provided under the terms of the MIT license
#
# Requires:
# - onkyo-eiscp - https://github.com/miracle2k/onkyo-eiscp
# - Eclipse Paho for Python - http://www.eclipse.org/paho/clients/python/
#

import sys
import argparse
import logging
import logging.handlers
import time
import json
import paho.mqtt.client as mqtt
import eiscp

version = "0.8"
lastSend = 0

class EiscpError(Exception):
    pass

def parse_args(raw_args=None):
    parser = argparse.ArgumentParser(description='Bridge between onkyo-eiscp and MQTT')

    parser.add_argument('--mqtt-host', default='localhost',
                        help='MQTT server address. Defaults to "localhost"')
    parser.add_argument('--mqtt-port', default='1883', type=int,
                        help='MQTT server port. Defaults to 1883')
    parser.add_argument('--mqtt-topic', default='onkyo/',
                        help='Topic prefix to be used for subscribing/publishing. '
                             'Defaults to "onkyo/"')
    parser.add_argument('--onkyo-address',
                        help='IP or hostname of the AVR. Defaults to autodiscover')
    parser.add_argument('--onkyo-id',
                        help='Device identifier of AVR to connecct to. Uses autodiscover')
    parser.add_argument('--onkyo-poll-interval', default=15, type=int,
                        help='Number of seconds to wait between cycles for EISCP traffic.  '
                             'Defaults to 15')
    parser.add_argument('--log',
                        help='set log level to the specified value. '
                             'Defaults to WARNING. Try DEBUG for maximum detail')
    parser.add_argument('--syslog', action='store_true',
                        help='enable logging to syslog')

    args = parser.parse_args(raw_args)
    if not args.mqtt_topic.endswith("/"):
        args.mqtt_topic += "/"
    return args

def setup_logging(args):
    if args.log:
        logging.getLogger().setLevel(args.log)
    if args.syslog:
        logging.getLogger().addHandler(logging.handlers.SysLogHandler())

def sendavr(receiver, cmd):
    global lastSend
    now = time.time()
    if (now - lastSend) < 0.05:
        time.sleep(0.05 - (now - lastSend))
    receiver.send(cmd)
    lastSend = time.time()
    logging.debug("Sent EISCP message %s" % (cmd))

def msghandler(mqc, userdata, msg):
    args = userdata['args']
    receiver = userdata['receiver']
    try:
        if receiver is None:
            raise EiscpError('no receiver currently connected')
        if msg.retain:
            return
        mytopic = msg.topic[len(args.mqtt_topic):]
        payload = msg.payload.decode()
        if mytopic == "command":
            sendavr(receiver, payload)
        elif mytopic[0:4] == "set/":
            llcmd = eiscp.core.command_to_iscp(mytopic[4:] + " " + payload)
            sendavr(receiver, llcmd)
    except Exception as e:
        logging.warning("Error processing MQTT message: %s" % e)

def connecthandler(mqc, userdata, flags, rc):
    logging.info("Connected to MQTT broker with rc=%d" % (rc))
    args = userdata['args']
    mqc.subscribe(args.mqtt_topic + "set/#", qos=0)
    mqc.subscribe(args.mqtt_topic + "command", qos=0)
    mqc.publish(args.mqtt_topic + "mqtt_connected", 2, qos=1, retain=True)

def disconnecthandler(mqc, userdata, rc):
    logging.warning("Disconnected from MQTT broker with rc=%d" % (rc))
    time.sleep(5)

def setup_mqtt(args):
    mqc = mqtt.Client(userdata={'receiver': None,
                                'args': args})
    mqc.on_message = msghandler
    mqc.on_connect = connecthandler
    mqc.on_disconnect = disconnecthandler
    mqc.will_set(args.mqtt_topic + "mqtt_connected", 0, qos=2, retain=True)
    mqc.connect(args.mqtt_host, args.mqtt_port, 60)
    mqc.publish(args.mqtt_topic + "mqtt_connected", 1, qos=1, retain=True)
    return mqc

def setup_eiscp(args):
    if args.onkyo_address:
        receiver = eiscp.eISCP(args.onkyo_address)
    else:
        logging.info('Starting auto-discovery of Onkyo AVRs')
        receivers = eiscp.eISCP.discover()
        for receiver in receivers:
            logging.info("Discovered %s at %s:%s with id %s" % (
                receiver.info['model_name'], receiver.host, receiver.port,
                receiver.info['identifier']))
        if args.onkyo_id:
            receivers = [r for r in receivers
                         if args.onkyo_id in r.info['identifier']]
        if len(receivers) == 0:
            raise EiscpError("No specified AVRs discovered")
        elif len(receivers) != 1:
            raise EiscpError("More than one AVR discovered, please specify "
                             "explicitely using --onkyo-address or --onkyo-id")
        receiver=receivers.pop(0)
        logging.info('Discovered AVR at %s', receiver)
    return receiver

def register_receiver(mqc, receiver, args):
    mqc.user_data_set({'receiver': receiver,
                       'args': args})

def eiscp_connect_handler(mqc, receiver, args):
    register_receiver(mqc, receiver, args)
    mqc.will_set(args.mqtt_topic + "eiscp_connected", 0, qos=2, retain=True)
    mqc.publish(args.mqtt_topic + "eiscp_connected", 1, qos=1, retain=True)

def eiscp_disconnect_handler(mqc, args):
    register_receiver(mqc, None, args)
    mqc.publish(args.mqtt_topic + "eiscp_connected", 0, qos=1, retain=True)

def publish(args, mqc, suffix, val, raw):
    robj = {"val": val}
    if raw is not None:
        robj["onkyo_raw"] = raw
    mqc.publish(args.mqtt_topic + "status/" + suffix, json.dumps(robj),
                qos=0, retain=True)
    logging.debug('Published %s to status/%s' % (repr(robj), suffix))

def read_from_eiscp(receiver, timeout):
    msg = receiver.get(timeout)
    while msg is not None:
        yield msg
        msg = receiver.get(timeout)

def main():
    args = parse_args()

    setup_logging(args)
    logging.info('Starting onkyo2mqtt V%s '
                 'with topic prefix \"%s\"' % (version, args.mqtt_topic))

    mqc = setup_mqtt(args)
    mqc.loop_start()

    while True:
        try:
            receiver = setup_eiscp(args)
            eiscp_connect_handler(mqc, receiver, args)

            # Query some initial values
            for icmd in ("PWR", "MVL", "SLI", "SLA", "LMD"):
                sendavr(receiver, icmd + "QSTN")

            for msg in read_from_eiscp(receiver, args.onkyo_poll_interval):
                try:
                    parsed = eiscp.core.iscp_to_command(msg)
                    # Either part of the parsed command can be a list
                    if isinstance(parsed[1], str) or isinstance(parsed[1], int):
                        val = parsed[1]
                    else:
                        val = parsed[1][0]
                    if isinstance(parsed[0], str):
                        publish(args, mqc, parsed[0], val, msg)
                    else:
                        for pp in parsed[0]:
                            publish(args, mqc, pp, val, msg)
                except:
                    publish(args, mqc, msg[:3], msg[3:], msg)
        except EiscpError as e:
            logging.warning(str(e))

        eiscp_disconnect_handler(mqc, args)
        logging.warning('EISCP connection went stale, retrying')
        time.sleep(5)

if __name__ == "__main__":
    main()
