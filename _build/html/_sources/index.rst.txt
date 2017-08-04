.. sdn_throwdown documentation master file, created by
   sphinx-quickstart on Fri Feb 24 20:21:08 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.
.. py:module:: link_class

Welcome to the MPLS Optimizer's documentation!
==============================================



This project is the build code for a Santa Clara University Team
For the 2017 Juniper Networks SDN Throwdown Silicon Valley Competition

The project optimizes your MPLS core network for inputted connections.
The application does this by monitoring your Core networks performance,
(Latency and Link Status) and changing customer LSP to lowest latency redundant open paths

Just run the Python Application with your server IP and credentials and go!

.. toctree::
   :maxdepth: 2
   :caption: Contents:



.. autofunction:: generate()

Program Logic
=============

Requirements:
-------------

The program needs to:
  #. Visualize the Network Topology.
  #. Validate connectivity between customer sites.
  #. Auto-Recover from topology link failures




Examples
========



Start by running module::

  python3 link_class.py

The optimizer will begin to initialize the topology and once complete show the Banner::

  *****************************************
  Welcome to the MPLS Optimizer developed by 14203 Broncos
  for the 2017 OpenLab SDN Throwdown
  This application dynamically responds to topology changes
  and ensures that the lowest latency redundant links are always provisioned for a customer LSP

  +-+-+-+-+-+-+-+ +-+-+ +-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+

  |P|o|w|e|r|e|d| |b|y| |J|u|n|i|p|e|r| |O|p|e|n|L|a|b|

  +-+-+-+-+-+-+-+ +-+-+ +-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+



                                                  .----.
                                               ./++++++++/.
                                              :++++++++++++:
                                       `.--..-//////oo//////-`...``
                                   `:+++++++sso///+oo+///+o+:::::::-
                                   .+++++++//+sss+/+oo+/+ooo/::::::///.
                                  `++++++++///osssss++osoooo-:::///////`
                                  .+////+oo+++osssyyyysyoss+///++/::://`
                                   ////////++++syyhhhhhhyys/////:::::::
                                   `:///////+ooshhdhhhhhhho++//:::::::`
                                     -/+++++++oshhhhhhhhhhso////////-
                                   `----:::/+ossyhhhhhhhhysso+:::-----`
                                   -------:////+osyhhhhhyoo////:-------
                                  `-----://///////oooooo//+//////:-----`
                                   ----::::---::::/++++/::::---:::::---
                                   `---------:::::-/++/-:::::---------`
                                     .-------:::---://:---:::-------.
                                        `````.------//------.`````
                                              .-----::-----.
                                               `.--------.`
                                                  ``..``

  .__   __.   ______   .______     .___________. __    __       _______..___________.    ___      .______
  |  \ |  |  /  __  \  |   _  \    |           ||  |  |  |     /       ||           |   /   \     |   _  |
  |   \|  | |  |  |  | |  |_)  |   `---|  |----`|  |__|  |    |   (----``---|  |----`  /  ^  \    |  |_)  |
  |  . `  | |  |  |  | |      /        |  |     |   __   |     \   \        |  |      /  /_\  \   |      /
  |  |\   | |  `--'  | |  |\  \----.   |  |     |  |  |  | .----)   |       |  |     /  _____  \  |  |\  \----.
  |__| \__|  \______/  | _| `._____|   |__|     |__|  |__| |_______/        |__|    /__/     \__\ | _| `._____|

  Enter a command or ? for help: ?

You are now ready to pass commands to the Optimizer!

Action Commands
---------------

The first action available is to enable responsive/dynamic path selection.
Entering this command will begin the background process to listen for link failures and repairs::

  Enter a command or ? for help: start responsive

  Listening for Link Events in the background!

The second command available is "topology reconverge".
This command is a manual trigger for the topology optimization and update process.
This will re-optimize and update the NorthStar Controller. Results should be similiar to::

  Enter a command or ? for help: topology reconverge
  Converging the Topology

  **********
  Optimum LSPs Found for  SF_to_NY :
  Gold 1 LSP: ['SF', 'LA', 'Houston', 'Tampa', 'Miami', 'Chicago', 'NY']
  Gold 2 LSP: ['SF', 'Dallas', 'Miami', 'NY']
  Silver LSP: ['SF', 'LA', 'Houston', 'Tampa', 'Miami', 'NY']
  Bronze LSP: ['SF', 'LA', 'Houston', 'Tampa', 'Miami', 'Dallas', 'Chicago', 'NY']
  Updating  GROUP_SIX_SF_NY_LSP4 on NorthStar Controller
  LSP Updated on NorthStar Controller
  Updating  GROUP_SIX_SF_NY_LSP3 on NorthStar Controller
  LSP Updated on NorthStar Controller
  Updating  GROUP_SIX_SF_NY_LSP1 on NorthStar Controller
  LSP Updated on NorthStar Controller
  Updating  GROUP_SIX_SF_NY_LSP2 on NorthStar Controller
  LSP Updated on NorthStar Controller
  New York can reach San Fransisco
  SF can reach New York
  **********
  Optimum LSPs Found for  NY_to_SF :
  Gold 1 LSP: ['NY', 'Chicago', 'Miami', 'Tampa', 'Houston', 'LA', 'SF']
  Gold 2 LSP: ['NY', 'Miami', 'Dallas', 'SF']
  Silver LSP: ['NY', 'Chicago', 'Miami', 'Tampa', 'Houston', 'LA', 'Dallas', 'SF']
  Bronze LSP: ['NY', 'Chicago', 'Miami', 'Tampa', 'Houston', 'Dallas', 'SF']
  Updating  GROUP_SIX_NY_SF_LSP4 on NorthStar Controller
  LSP Updated on NorthStar Controller
  Updating  GROUP_SIX_NY_SF_LSP3 on NorthStar Controller
  LSP Updated on NorthStar Controller
  Updating  GROUP_SIX_NY_SF_LSP1 on NorthStar Controller
  LSP Updated on NorthStar Controller
  Updating  GROUP_SIX_NY_SF_LSP2 on NorthStar Controller
  LSP Updated on NorthStar Controller
  New York can reach San Fransisco
  SF can reach New York

Classes
=======

Topology
--------

.. autoclass:: Topology
  :members:

TopologyLink
------------

.. autoclass:: TopologyLink
  :members:

TopologyNode
------------

.. autoclass:: TopologyNode
  :members:

Connection
----------

.. autoclass:: Connection
  :members:

PossibleLSP
-----------

.. autoclass:: PossibleLSP
  :members:

Public Functions
================

.. autofunction:: find_all_paths

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
