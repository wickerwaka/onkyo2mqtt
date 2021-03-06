onkyo2mqtt
==========

  Written and (C) 2015-16 Oliver Wagner <owagner@tellerulam.com>
  Enhancements copyright 2018-19 Jeff Licquia <jeff@licquia.org>
  
  Provided under the terms of the MIT license.

Overview
--------
Bridge between the Onkyo AVR EISCP remote control protocol and MQTT.
Allows to remotely control networked Onkyo AVRs and get status
information.

It's intended as a building block in heterogenous smart home environments where 
an MQTT message broker is used as the centralized message bus. See 
https://github.com/mqtt-smarthome for a rationale and architectural overview.


Prerequisites
-------------
* Python 2.7+.  Tested and working under Python 3.6.
* onkyo-eiscp - https://github.com/miracle2k/onkyo-eiscp (implements
  the Onkyo EISCP protocol and command translation)
* Eclipse Paho for Python - http://www.eclipse.org/paho/clients/python/
  (used for MQTT communication)


MQTT Message format
--------------------
The message format generated is a JSON encoded object with the following members:

* val - the actual value
* onkyo_raw - the raw EISCP command before parsing by onkyo-eiscp  


Command parsing and topics
--------------------------
The onkyo-eiscp module by miracle2k provides sophisticated parsing which
translated the raw EISCP commands into readable strings. Please see the
module page at https://github.com/miracle2k/onkyo-eiscp for more
information about that.

onkyo2mqtt will translate incoming EISCP status events into their
textual representation, and publish those via MQTT.

For example, the raw "power is off" status is published into 
the topic "\<prefix\>/status/system-power" as follows:

    {"onkyo_raw": "PWR00", "val": "standby"}

Sending commands is possible in three ways:

1. By publishing a value into a textual topic ("\<prefix\>/set/\<topic\>") with a new value
2. By publishing into the special topic "\<prefix\>/command" with a
textual command as described in https://github.com/miracle2k/onkyo-eiscp#commands
3. By publishing a raw EISCP command into the special "\<prefix\>/command" topic

Special topics "\<prefix\>/eiscp_connected" and
"\<prefix\>/mqtt_connected" are maintained.  Each is "0" or "1" for
false or true, respectively.


Error handling
--------------
onkyo2mqtt will attempt to reconnect when it loses its connection to
either the AVR or the MQTT broker, or if it cannot establish either
connection at startup.  The current status of both connections is
published at the topics "\<prefix\>/eiscp_connected" and
"\<prefix\>/mqtt_connected".


Usage
-----

    --mqtt-host MQTT_HOST
                        MQTT server address. Defaults to "localhost"
    --mqtt-port MQTT_PORT
                        MQTT server port. Defaults to 1883
    --mqtt-topic MQTT_TOPIC
                        Topic prefix to be used for subscribing/publishing.
                        Defaults to "onkyo/"
    --onkyo-address ONKYO_ADDRESS
                        IP or hostname of the AVR. Defaults to autodiscover
    --onkyo-id ID
                        Device identifier of AVR to connecct to. Uses autodiscover
    --log LOG           set log level to the specified value. Defaults to
                        WARNING. Try DEBUG for maximum detail                        
                        
Changelog
---------
* 0.10 - 2019/12/31 - licquia
  - Fix EISCP connection retries.

* 0.9 - 2019/05/11 - licquia
  - Do MQTT connection status differently.

* 0.8 - 2018/11/23 - licquia
  - Massive reformatting and refactoring of the code structure and whitespace.
  - Updates to accomodate paho-mqtt changes.
  - Handle text encoding/decoding properly.
  - Retry EISCP connection failures, instead of exiting.
  - Publish MQTT and EISCP connection status in MQTT.

* 0.7 - 2016/06/05 - owagner
  - support --onkyo-id

* 0.6 - 2015/06/07 - owagner
  - deal with onkyo-eiscp returning an int as an argument

* 0.5 - 2015/04/04 - owagner
  - removed reconnect() call in onDisconnected -- Paho will reconnect on it's own
  anyway, and an exception during reconnect would actually kill the service
  thread

* 0.4 - 2015/01/25
  - adapted to new mqtt-smarthome topic hierarchy scheme with set/ and
    status/ function prefixes, and connected being an enum

* 0.3 - 2014/12/28
  - set <prefix>/connected topic
  - add new option "--log" to set the log level
  - implement MQTT-side reconnect handling

* 0.2 - 2014/12/28
  - maintain a minimum of 50ms wait time between commands
  
