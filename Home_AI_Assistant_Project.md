# Home AI Assistant Project

## 1. The Idea

Build a private, DIY **Home AI Assistant** that runs from an old laptop
and gradually becomes the central brain of the house.

The first goal is intentionally simple:

> **When Tayo arrives home, the system recognizes that he is home. When
> he says "Hello," the house responds through a speaker with a
> personalized greeting.**

Example:

**Tayo:** "Hello."

**Home Assistant:** "Welcome home, Tayo. How was your day?"

We will get this basic interaction working first. After that, we can
gradually connect the assistant to the TV, lights, AC, electricity
monitoring, sensors, and other household systems.

------------------------------------------------------------------------

## 2. Design Principle

We are **not** trying to buy a complete commercial smart-home system.

We will build our own modular system.

The old laptop will be the **brain**. Other devices will connect to it
over the home network.

``` text
                    HOME
                      |
               HOME Wi-Fi / LAN
                      |
               +------v------+
               | OLD LAPTOP  |
               | Home Brain  |
               +------+------+
                      |
          +-----------+-----------+
          |           |           |
        Phone       Voice       Devices
          |        Mic/Speaker     |
          |                       |
      Presence              TV / Sensors /
      Detection             AC / Lights / etc.
```

The laptop does **not** need to be dismantled. It can remain intact and
stay somewhere in the house as a server.

------------------------------------------------------------------------

## 3. Phase 1: Recognize Me and Greet Me

### Objective

Create this sequence:

``` text
Tayo arrives home
        |
        v
Phone is detected at home
        |
        v
Old laptop knows "Tayo is home"
        |
        v
Tayo says "Hello"
        |
        v
Microphone captures speech
        |
        v
Voice system recognizes the command
        |
        v
Assistant generates/selects response
        |
        v
External speaker says:
"Welcome home, Tayo."
```

### How the system can recognize arrival

For the first prototype, use the **phone as the presence identifier**.

Possible methods include:

-   Home Assistant phone presence
-   Wi-Fi/network presence
-   Bluetooth presence

We should start with the simplest reliable method supported by the phone
and home network. Later, multiple signals can be combined to reduce
false arrival/departure detections.

### Voice input

The system needs a microphone to hear "Hello."

If the laptop microphone works, use it initially.

If it does not work or its location makes voice pickup poor, add an
external USB microphone or, later, dedicated room voice hardware.

### Voice output

The laptop's broken speaker is not a problem.

Use:

-   an existing Bluetooth speaker, or
-   a small USB/3.5 mm powered speaker.

The speaker becomes the assistant's voice.

------------------------------------------------------------------------

## 4. Core Software

### Home Assistant

Home Assistant will be the main smart-home platform.

It will manage:

-   presence
-   devices
-   sensors
-   automations
-   routines
-   events
-   states

Official site: https://www.home-assistant.io/

### Voice Layer

The voice system will eventually perform:

``` text
Speech
   |
   v
Speech-to-Text
   |
   v
Intent / AI
   |
   v
Home Assistant action or conversational response
   |
   v
Text-to-Speech
   |
   v
Speaker
```

For the first prototype, the greeting does not need a powerful cloud AI
model. A deterministic automation can handle "Hello." AI can be added
where natural-language reasoning is actually useful.

------------------------------------------------------------------------

## 5. Phase 1 Hardware

### Already available

-   Old laptop
-   Smartphone
-   Home Wi-Fi/router

### Need to check

-   Does the laptop microphone work?
-   Does the laptop reliably connect to Wi-Fi/Ethernet?
-   Can the laptop remain powered for long periods?
-   What operating system/specifications does it have?

### May need

-   External speaker
-   USB microphone

We should **not buy ESP32 boards, Raspberry Pis, sensors, smart relays,
or other hardware yet**.

First make the basic home brain work.

------------------------------------------------------------------------

## 6. Phase 2: Make the Greeting Intelligent

After basic arrival detection and voice response work, the greeting can
use household context.

Instead of:

> "Welcome home, Tayo."

It could eventually say:

> "Welcome home, Tayo. Grid power is currently available."

or:

> "Welcome home. You have an appointment at 8 PM."

or:

> "Welcome home. You stopped your movie at 48 minutes yesterday."

The important distinction is:

**Presence detection tells the house WHO/WHEN.**

**Sensors and connected services provide CONTEXT.**

**AI decides how to communicate or reason about that context when
needed.**

------------------------------------------------------------------------

## 7. Phase 3: Connect the TV

The Hisense TV can become one of the assistant's controlled devices.

Possible control methods depend on the exact TV model and operating
system:

-   network/LAN control
-   supported Home Assistant integration
-   Wake-on-LAN/network wake where supported
-   infrared control using an ESP32/IR transmitter

Target interaction:

> "Continue my movie."

Possible workflow:

``` text
Voice command
     |
     v
Home AI Assistant
     |
     +--> Turn TV on
     |
     +--> Open movie interface
     |
     +--> Identify last watched movie
     |
     +--> Retrieve saved playback position
     |
     +--> Resume playback
```

Because the movie website is our own system, we can design an
API/integration between it and the Home AI Assistant.

------------------------------------------------------------------------

## 8. Phase 4: Give the House Senses

Add inexpensive sensors gradually.

### Presence sensors

Determine whether someone is actually in a room.

Possible uses:

-   automatic lighting
-   AC control
-   occupancy awareness
-   room-specific voice responses

### Temperature and humidity

Allow commands such as:

> "What's the temperature in my room?"

And automations such as:

``` text
Room occupied
+
Temperature above threshold
+
Appropriate power source available
        |
        v
AC automation
```

### Door sensors

Know when selected doors open or close.

### Electricity monitoring

Eventually detect:

-   grid power available
-   grid outage
-   grid restoration
-   inverter state
-   battery information, where the inverter exposes compatible data
-   power history

------------------------------------------------------------------------

## 9. Phase 5: Give the House Hands

Once the assistant can sense the environment, add controlled devices.

Examples:

### TV

> "Turn on the TV."

### AC

> "Make the bedroom cooler."

### Lights

> "Turn off the living-room lights."

### Smart plugs

> "Turn off the fan."

For 230 V mains electricity, we will use properly rated
enclosed/certified smart devices or professional electrical
installation. We will **not** connect exposed DIY ESP32/Arduino circuits
directly to household mains.

------------------------------------------------------------------------

## 10. Phase 6: Routines

Individual commands can be combined into routines.

### "Good night"

``` text
"Good night"
      |
      +--> TV off
      +--> selected lights off
      +--> AC set appropriately
      +--> selected devices checked
      +--> tomorrow's schedule checked
      +--> alarm/reminders prepared
```

### "I'm leaving"

``` text
"I'm leaving"
      |
      +--> TV off
      +--> AC off
      +--> selected lights off
      +--> selected appliances checked
      +--> house enters Away mode
```

### Arrival

``` text
Tayo detected
      |
      +--> Home mode
      +--> assistant ready
      +--> relevant environmental state checked
      |
Tayo: "Hello"
      |
      v
Personalized greeting
```

------------------------------------------------------------------------

## 11. Long-Term Architecture

``` text
                         +----------------+
                         |   TAYO HOME AI |
                         +--------+-------+
                                  |
                         +--------v-------+
                         |   OLD LAPTOP   |
                         |                |
                         | Home Assistant |
                         | Voice          |
                         | AI             |
                         | Automations    |
                         +--------+-------+
                                  |
                              Home LAN
                                  |
          +-------------+---------+---------+-------------+
          |             |                   |             |
          v             v                   v             v
        Phone          TV               ESP32s        Voice Nodes
          |                                  |
     Presence                       +--------+--------+
                                    |        |        |
                                 Sensors    IR     Low-voltage
                                    |      Control    interfaces
                                    |
                           +--------+---------+
                           |        |         |
                        Presence  Temp      Doors
```

------------------------------------------------------------------------

## 12. Development Roadmap

### Milestone 1 --- Home Brain

Install and configure the old laptop as the always-on home server.

### Milestone 2 --- Presence

Make the system reliably determine:

> **Tayo = Home**

and

> **Tayo = Away**

### Milestone 3 --- Voice

Make the system hear:

> "Hello."

and speak:

> "Welcome home, Tayo."

### Milestone 4 --- Better Conversation

Add natural-language capabilities where useful.

### Milestone 5 --- TV

Connect the Hisense TV and the existing movie application.

### Milestone 6 --- Sensors

Start adding ESP32-based sensors and room awareness.

### Milestone 7 --- Household Devices

Lights, AC, selected plugs, electricity/inverter monitoring, etc.

### Milestone 8 --- Home Intelligence

Create contextual automations so the house increasingly acts without
needing explicit commands.

------------------------------------------------------------------------

## 13. What We Do Next

Do **not buy anything yet**.

First inspect the old laptop and determine:

1.  Laptop model/specifications
2.  Current operating system
3.  Whether Wi-Fi works
4.  Whether the microphone works
5.  Available USB ports
6.  Whether it can remain powered continuously

Then we decide how Home Assistant should run on it and build **Milestone
1**.

The immediate target remains simple:

> **Walk into the house → system knows Tayo is home → say "Hello" →
> house answers.**

Everything else will be built on top of that working foundation.
