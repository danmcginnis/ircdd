.. Database

Database
********

``IRCDD`` uses two data-handling services for its operation: ``RethinkDB`` for data storage and consistency and ``NSQ`` for message passing. The following section describes their usage in the overall service.

RethinkDB:
==========

``RethinkDB`` is a JSON-oriented database - that is, it stores data in JSON documents as opposed to rows and columns.
Below is a description of each table and the structure of the documents stored within.

Tables and Documents:
---------------------

0. users:
   The ``users`` table contains avatar data for each user connected to the server. The documents in that table
   have the following structure and represent a persistent user state:

   .. code-block:: guess

       {
           "id": <string: primary key, matches the user's nickname>,
           "nickname": <string: the user's nickname>,
           "email": <string: the user's email; used only if registered>,
           "password": <string: the user's password; used only when registered>,
           "registered": <boolean: whether the user is registered or not>,
           "permissions": <dict: the user's permissions>
       }

1. user_sessions:
   The ``user_sessions`` table contains runtime objects that monitor the session of each active user. The documents 
   in this talbe have the following structure:

   .. code-block:: guess

       {
           "id": <string: primary key, matches the id of the user for whom this session applies>,
           "last_heartbeat": <datetime: the last time this session was active>,
           "last_message": <datetime: the last time the user posted a message>,
           "session_start": <datetime: when this session was created.
       }

2. groups:
   The ``groups`` table contains data for each group that exists on the server. The documents in that dable have
   the following structure and represent a persistent state:

   .. code-block:: guess

       {
           "id": <string: primary key, the name of the group>,
           "name": <string: the name of the group, matches the PK>,
           "type": <string: the type of the channel - either private or public>
           "meta": { <dict: meta information on the group>
              "topic": <string: the current topic of the group>,
              "topic_author": <string: the nickname of the user who authored the topic>,
              "topic_time": <datetime: the time the topic was set>
           }
       }

3. group_states:
   The ``group_states`` table contains runtime data for the groups on the server, specifically which users are
   connected to which group. The documents in that table have the following structure:

   .. code-block:: guess
   
       {
           "id": <string: primary key, matches the id of the group for whom this state applies>,
           "users": { <dict: a map of users and their last activity in the group>
               "<string: the user's nickname>": {
                   "heartbeat": <datetime: the last time this user was active in the group>
               }
       }

Purpose
-------

This sections describes how ``IRCDD`` uses ``RethinkDB``. 

Firstly, ``RethinkDB`` serves to store group and user data. This is the group and user profiles and metadata found in the ``groups`` and ``users`` tables, as well as the session data found in ``user_sessions`` and ``group_states``.

Secondly, ``RethinkDB`` is used to solve the consensus problem between ``IRCDD`` instances. ``RethinkDB`` is the authority on any data, including time (this avoiding the need for vector clocks).

Lastly, ``RethinkDB`` is used in an Observer pattern between itself and the ``IRCDD`` instances for events that require consistency. For example, setting the topic of a group needs to succeed in the database cluster before subscribers to that group are notified of it happening. 


NSQ Topics:
===========

Message Structure and Message Types:
------------------------------------

Messages published and pulled from ``NSQ`` are Python dictionaries which exist as JSON in their serialized state. Messages on ``NSQ`` represent events that must be multicasted to different subscribers. The queues (topics as ``NSQ`` calls them) represent subscription channels, on which multiple subscribers can listen for an event. On publishing a message on a given topic, all observers receive a copy - the messages are multicasted. The message queue effectively bypasses the need to
establish consensus, so only events that do not require that can be published. For instance, a user publishing a message to a chat channel does not need to establish consensus. A user trying to set the topic of a channel does need to have their operation acknowledged - therefore that event cannot go through the message queue.

``IRCDD`` nodes use ``NSQ`` in the following way: each instance subscribes to the topics that its connected users and groups represent. On receiving a message on a given topic, the ``IRCDD`` instance processes the message and notifies the appropriate parties of the event.

For example, take the following setup: three ``IRCDD`` servers, one IRC channel called ``demoroom``, and three users, each connected to a different server, and each "joined" to ``demoroom``. When a user publishes a message to ``demoroom``, the ``IRCDD`` server that they are connected to pushes a message containing the publish event to the message queue ``demoroom``. The other two ``IRCDD`` servers - which are listening for messages on ``demoroom`` - each receive the message, unpack the event, and forward it to their connected users.

The actual message that gets serialized to JSON has the following structure:

.. code-block:: guess

    {
        "type": <string: the type of the message, one of [privmsg, join, part]>,
        "sender": { <dict: information about the sender>
            "name": <string: the name of the sender>,
            "hostname": <string: the hostname of the instance that emitted the message, e.g. instance-1>, 
        },
        "text": <string: present only in /privmsg messages, the text of the message>
        "reason": <string: present only in /part messages, the reason the user disconnected>
    }
