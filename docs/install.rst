.. Installation Guide

Installation Guide
******************

``IRCDD`` was designed to run as a service under ``CoreOS`` alongside a set of support
services, forming a full service stack. This guide will walk you through installing an ``IRCDD`` 
service cluster on an existing ``CoreOS`` cluster using both the pre-built Docker container and
building everything from source.

Obtain the latest release:
==========================

Releases are tagged on the ``master`` branch and packaged with Guthub's releases feature. A release of ``IRCDD`` contains
the source code, this documentation, ``fleet`` service files with sensible default settings, and the build files for the three
``Docker`` containers that make up the system.

Download and unarchive the latest release found here:

https://github.com/kzvezdarov/ircdd/releases

Installation and Deployment:
============================

The section assumes that you have SSH access to a ``CoreOS`` cluster. It will walk you through the
process of obtaining, modifying, and starting the services needed to run the ``IRCDD`` cluster using
the pre-built container.

The ``IRCDD`` cluster is made up of services that run on the ``CoreOS`` infrastructure. Each service runs 
its own ``Docker`` container and clusters with the rest via shared configuration in ``ETCD``. This means that to 
deploy an ``IRCDD`` cluster, you simply need to load the appropriate service files into ``fleet`` and start the 
desired number of instances. 

The distinct services in an ``IRCDD`` cluster are the ``NSQ`` cluster - made up of ``NSQD`` and ``NSQLookupd`` nodes; 
the ``RethinkDB`` cluster - made up of ``RethinkDB`` instances; and the ``IRCDD`` instances that server the IRC requests.
The ``RethinkDB`` and ``NSQ`` clusters do not communicate with eachother and serve the ``IRCDD`` instances as discrete, 
unified resources. That is, as long as the ``IRCDD`` instances have access to at least one ``RethinkDB`` node, one ``NSQLookupd`` node, and one ``NSQD`` node, they can function.


Deploying using the prebuilt containers:
----------------------------------------

The ``IRCDD`` project provides some prebuilt containers for each service. The containers are configured to cluster
together automatically and reload on configuration changes.

The prebuilt containers have sensible default settings and are good for quickly getting your feet wet with the system.
Deploying the ``IRCDD`` cluster in that case is fairly trivial:

1. Modify the service files found in the ``scripts/services`` directory to suit your needs.

2. Copy the service files to one node of your cluster (skip this step if you have forwarded ``fleet``).

3. SSH into the node on which the files reside and submit them to ``fleet``.

4. Proceed to start the services: :ref:`cluster-start`


Building the containers from source:
------------------------------------

For a real deployment, you will likely want to custumize the configration of each service and build custom containers,
integrated with your release cycle. 

1. Modify the container files and build script to suit your needs. The build scripts and files for each service container
   are found in ``scripts/containers``. Refer to :doc:`config` for details.

2. Modify the service files found in ``scripts/services`` to suit your needs. You will need to change the name of the 
   repository from which to pull the containers to yours. That is, this:

   .. code-block:: guess
    
       ExecStartPre=/usr/bin/docker pull kzvezdarov/ircdd-confd

   needs to be changed to this:

   .. code-block:: guess
      
       ExecStartPre=/usr/bin/docker pull my-custom-repo/ircdd-confd

   Do that for the ``ExecStart`` line and any directives that reference the old repository names.

3. After this is done and you have confirmed that your containers built successfully, copy the
   service files to one of your ``CoreOS`` instances.

4. After the files are copied, ssh into ``CoreOS`` and submit them to ``fleet``.

5. Proceed to start the services: :ref:`cluster-start`

.. _cluster-start:

Starting the cluster:
---------------------

Now that all service templates are loaded in, it is time to start the service stack. Note that at the
first startup of each service its container will be downloaded, which takes some time.

1. First, start the ``RethinkDB`` cluster. Start a single node:
   
    .. code-block:: shell-session

       fleetctl start rethinkdb@1
       fleetctl start rethinkdb-discovery@1

   The first node will see that no other nodes are registered with ``ETCD``, register itself, 
   build its data directory, start up, and import the base table structure.

   Once the service is ``active`` and ``running``, start the rest of the nodes:

    .. code-block:: shell-session

       fleetctl start rethinkdb@{2..N}
       fleetctl start rethinkdb-discovery@{2..N}
    
   where N is the total number of desired nodes. These secondary nodes will find that there
   already are ``RethinkDB`` nodes registered in ``ETCD``, start up and join with the existing members.

6. The ``NSQ`` cluster is started in a similar manner. Because ``NSQLookupd`` instances do not need to know of
   eachother, everything can be started at the same time:

    .. code-block:: shell-session
   
       fleetctl start nsqlookupd@{1..N}
       fleetctl start nsqlookupd-discovery@{1..N}

   where N is the desired number of lookup nodes. The ``NSQLookupd`` nodes will
   start up and register with ``ETCD``.
   
   To start the ``NSQD`` nodes:

    .. code-block:: shell-session

       fleetctl start nsqd

   The ``NSQD`` service is configured as global by default, which means it will automatically be scheduled to run 
   on every machine in the cluster. The ``NSQD`` nodes will check for ``NSQLookupd`` nodes in ``ETCD`` and join with those 
   on startup. Finally, the ``NSQD`` nodes register themselves in ``ETCD``.

7. Finally, to start the ``IRCDD`` nodes:
   
    .. code-block:: shell-session

       fleetctl start ircdd{1..N}

   where N is the desired number of nodes.
   
   The ``IRCDD`` nodes will check for available ``NSQLookupd`` and ``RethinkDB`` instances in ``ETCD``'s registry,
   connect with those, and start up the actual IRC server. Note that ``IRCDD`` assumes that there is a local ``NSQD``
   instance.
