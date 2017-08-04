"""
Class that repersents topology, nodes and links
"""
import json
import requests
import redis
import webbrowser
import threading
import paramiko
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.pyplot import pause
from pprint import pprint
requests.packages.urllib3.disable_warnings()

class PingTest:
    """Ping test for connectivity between VM """
    ssh = ""
    def __init__(self, host_ip, uname, passwd):
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(host_ip, username=uname, password=passwd)
            #print "In init function"
        except (paramiko.BadHostKeyException, paramiko.AuthenticationException,
                paramiko.SSHException) as e:
            print (str(e))
            sys.exit(-1)

    def callSF(self,cmd):
        try:
            channel = self.ssh.invoke_shell()
            timeout = 60 # timeout is in seconds
            channel.settimeout(timeout)
            newline        = '\r'
            line_buffer    = ''
            channel_buffer = ''
            channel.send(cmd + ' ; exit ' + newline)
            testResult=[]

            while True:
                channel_buffer = channel.recv(1).decode('UTF-8')
                if len(channel_buffer) == 0:
                    break
                channel_buffer  = channel_buffer.replace('\r', '')
                if channel_buffer != '\n':
                    line_buffer += channel_buffer
                else:
                    result = line_buffer.split('\n')
                    testResult.append(result)
                    #print (line_buffer)
                    line_buffer   = ''
            targetString=['From 10.10.2.205 icmp_seq=1 Destination Host Unreachable']
            if targetString == testResult[22]:
                print("New York cannot reach San Fransisco")
            else:
                print("New York can reach San Fransisco")

        except paramiko.SSHException as e:
            print (str(e))
            sys.exit(-1)

    def callNY(self,cmd):
        try:
            channel = self.ssh.invoke_shell()
            timeout = 60 # timeout is in seconds
            channel.settimeout(timeout)
            newline        = '\r'
            line_buffer    = ''
            channel_buffer = ''
            channel.send(cmd + ' ; exit ' + newline)
            testResult=[]
            while True:
                channel_buffer = channel.recv(1).decode('UTF-8')
                if len(channel_buffer) == 0:
                    break
                channel_buffer  = channel_buffer.replace('\r', '')
                if channel_buffer != '\n':
                    line_buffer += channel_buffer
                else:
                    result = line_buffer.split('\n')

                    testResult.append(result)
                    #print (line_buffer)
                    line_buffer   = ''

            targetString=['From 10.10.2.225 icmp_seq=1 Destination Host Unreachable']
            if targetString == testResult[22]:
                print("SF cannot reach New York")
            else:
                print("SF can reach New York")

        except paramiko.SSHException as e:
            print (str(e))
            sys.exit(-1)


class Topology():
    """
    class that repersents the overall network topology
    """

    def __init__(self, controller_ip, username, password):
        self.controller_ip = controller_ip
        self.nodes = {}
        self.node_to_ip = {}
        self.ip_to_node = {}
        self.links = {}
        self.username = username
        self.password = password
        self.api_auth_key = self.get_api_auth_key()
        self.graph = self.build_graph()
        self.connections = {}
        self.initialize_topology()

    def get_api_auth_key(self):
        """ Method creates the auth key, hard coded for group6::

                print(TOPO.get_api_auth_key())

         """
        url = "https://" + self.controller_ip + ":8443/oauth2/token"
        payload = {'grant_type': 'password',
                   'username': self.username, 'password': self.password}
        response = requests.post(
            url, data=payload,
            auth=(self.username, self.password),
            verify=False)
        json_data = json.loads(response.text)
        auth_header = {
            "Authorization": "{token_type} {access_token}".format(**json_data)}
        return auth_header

    def listen_and_respond_to_link_events(self):
        """ Method that listens to redis for link events.
            When link events happen (failure or healing) re-converge the topology.
            After reconverging deploy the new optimum LSP onto the network
        """
        print("\nListening for Link Events in the background!\n")
        rredis = redis.StrictRedis(host='10.10.4.252', port=6379, db=0)
        pubsub = rredis.pubsub()
        pubsub.subscribe('link_event')
        for item in pubsub.listen():
            if item['data'] != 1:
                data = item['data'].decode('utf-8')
                data = json.loads(data)
                print(data['router_name'], " : ", data['status'])
                if data['status'] == "failed":
                    print("\nLink failure detected! Reconverging Topology\n")
                elif data['status'] == "healed":
                    print("\nLink repair detected! Reconverging Topology\n")
                self.update_link_status()
                self.update_latency()
                self.converge_and_apply_lsp()

    def initialize_topology(self):
        """
        Method that starts the Topology. This gets all nodes, links, default connections
        and populates their default values
        """
        # TODO Optimize these and their performance. Currently takes 2 minutes
        # for initization
        print("Initializing Topology...")
        self.get_and_build_nodes()
        self.get_and_build_links()
        self.build_node_connections()
        self.update_link_status()
        self.update_latency()
        Connection(self, "SF", "NY")
        Connection(self, "NY", "SF")
        for con in self.connections:
            for lsp in self.connections[con].possible_paths:
                lsp.update_lsp_metrics()
            self.connections[con].find_and_set_class_lsps()

    def converge_and_apply_lsp(self):
        """ Function that gets and converges the network to find optimum LSPs.
            calls::

                self.connections.find_and_set_class_lsps()
                self.update_link_status()
                self.update_latency()

        """
        print("Converging the Topology\n")

        for connection in self.connections:
            for path in self.connections[connection].possible_paths:
                path.update_lsp_metrics()
            self.connections[connection].find_and_set_class_lsps()
            # Send Bronze
            self.send_lsp_update(
                "GROUP_SIX_" + self.connections[
                    connection].start + "_" + self.connections[
                        connection].end + "_LSP4", self.connections[
                            connection].bronze_path.ero_format)

            # Send Silver
            self.send_lsp_update(
                "GROUP_SIX_" + self.connections[
                    connection].start + "_" + self.connections[
                        connection].end + "_LSP3", self.connections[
                            connection].silver_path.ero_format)
            # Send Gold paths
            i = 1
            for lsp in self.connections[connection].gold_paths:
                self.send_lsp_update(
                    "GROUP_SIX_" + self.connections[
                        connection].start + "_" + self.connections[
                            connection].end + "_LSP" + str(i), self.connections[
                                connection].gold_paths[lsp].ero_format)
                i = i + 1
            ping_vms()

    def send_lsp_update(self, lsp_name, ero_input):
        """ Sends the API call for updating ERO for LSPs
            Input is the ero array that is to be sent.

            expected format::

                    ero= [
                                    { 'topoObjectType': 'ipv4', 'address': '10.210.15.2'},
                                    { 'topoObjectType': 'ipv4', 'address': '10.210.13.2'},
                                    { 'topoObjectType': 'ipv4', 'address': '10.210.17.1'}
                                   ]

        Updates the northstar controller with the new LSPs.

        Uses https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1/te-lsps/ API
        And updates only GROUP_SIX ERO

        ERO Name/ Number mapping to Class ranking (same for both directions):

        LSP1: Gold One: The lowest Latency link.
                  Intended for real time applications
        LSP2: Gold Two: The second lowest latency redundant link from gold One
                  Intended for real time and business critical applications
        LSP3: Silver: The second lowest latency link that is not Gold Two
                  Intended for business relevant applications
        LSP4: Bronze: The third lowest latency link that is neither gold one, gold two or silver
                  Intended for scavenger class applications
        """
        print("Updating ", lsp_name, "on NorthStar Controller")
        requs = requests.get(
            'https://' + self.controller_ip +
            ':8443/NorthStar/API/v1/tenant/1/topology/1/te-lsps/',
            headers=self.api_auth_key, verify=False)
        dump = json.dumps(requs.json())
        lsp_list = json.loads(dump)
        # Find target LSP to use lspIndex
        for lsp in lsp_list:
            if lsp['name'] == lsp_name:
                break
        # Fill only the required fields
        ero = ero_input
        new_lsp = {}
        for key in ('from', 'to', 'name', 'lspIndex', 'pathType'):
            new_lsp[key] = lsp[key]

        new_lsp['plannedProperties'] = {
            'ero': ero
        }
        response = requests.put(
            'https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1/te-lsps/' + str(new_lsp[
                'lspIndex']),
            json=new_lsp, headers=self.api_auth_key, verify=False)
        print("LSP Updated on NorthStar Controller")

    def build_graph(self):
        """
        Method builds the graphing dictionary for routing algorithms
        """
        graph = {}
        for node in self.nodes:
            graph.update(self.nodes[node].connections)
        return graph

    def get_and_build_nodes(self):
        """
        Method that makes a api call into Northstar topology
        parses results and add unknown nodes into the topology node array
        """
        print("Building nodes...")
        req = requests.get(
            'https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1',
            headers=self.api_auth_key, verify=False)
        data = req.json()
        for each in data["nodes"]:
            node_name = (each["hostName"])
            if node_name not in self.nodes:
                node_ip = each["name"]
                node_lat = each["topology"]["coordinates"]["coordinates"][0]
                node_long = each["topology"]["coordinates"]["coordinates"][1]
                self.nodes.update(
                    {node_name: TopologyNode(
                        node_name, node_lat, node_long, node_ip, {node_name: []})})
                self.node_to_ip.update({node_name: node_ip})
                self.ip_to_node.update({node_ip: node_name})

    def build_node_connections(self):
        """ For each node collect what nodes it connects to """
        print("Building CE/PE Connections...")
        req = requests.get(
            'https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1',
            headers=self.api_auth_key, verify=False)
        node_connections = {}
        data = req.json()
        for each in data["nodes"]:
            node_name = (each["hostName"])
            node_connections.update({node_name: []})
            for links in data["links"]:
                if links["endA"]["node"]["name"] == self.node_to_ip[node_name]:
                    node_connections[node_name].append(
                        self.ip_to_node[links['endZ']["node"]["name"]])
                if links["endZ"]["node"]["name"] == self.node_to_ip[node_name]:
                    node_connections[node_name].append(
                        self.ip_to_node[links['endA']["node"]["name"]])
        for node in node_connections:
            for nod3 in self.nodes:
                if node == nod3:
                    for n0de in node_connections[node]:
                        self.nodes[node].connections[node].append(n0de)

    def get_and_build_links(self):
        """
        Method the makes api call to get topology links
        Then creates link objects and adds to topology
        """
        print("Building links...")
        req = requests.get(
            'https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1/links',
            headers=self.api_auth_key, verify=False)
        data = req.json()
        for each in data:
            from_node = each["endA"]["node"]["name"]
            from_ip = each["endA"]["ipv4Address"]["address"]
            to_node = each["endZ"]["node"]["name"]
            to_ip = each["endZ"]["ipv4Address"]["address"]
            if to_node in self.node_to_ip:
                to_node = self.node_to_ip[to_node]
            if from_node in self.node_to_ip:
                from_node = self.node_to_ip[from_node]
            link_name = from_node + "_to_" + to_node
            if link_name not in self.links:
                self.links.update({link_name: TopologyLink(
                    from_node, from_ip, to_node, to_ip)})
            # And now in reverse :D
            from_node = each["endZ"]["node"]["name"]
            from_ip = each["endZ"]["ipv4Address"]["address"]
            to_node = each["endA"]["node"]["name"]
            to_ip = each["endA"]["ipv4Address"]["address"]
            if to_node in self.node_to_ip:
                to_node = self.node_to_ip[to_node]
            if from_node in self.node_to_ip:
                from_node = self.node_to_ip[from_node]
            link_name = from_node + "_to_" + to_node
            if link_name not in self.links:
                self.links.update({link_name: TopologyLink(
                    from_node, from_ip, to_node, to_ip)})

    def update_link_status(self):
        print("Updating Link Status...")
        """ Method makes API call into northstar and get link status """
        req = requests.get(
            'https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1/links',
            headers=self.api_auth_key, verify=False)
        data = req.json()
        for link in data:
            from_node = link["endA"]["node"]["name"]
            to_node = link["endZ"]["node"]["name"]
            status = link["operationalStatus"]
            if to_node in self.node_to_ip:
                to_node = self.node_to_ip[to_node]
            if from_node in self.node_to_ip:
                from_node = self.node_to_ip[from_node]
            link_name = from_node + "_to_" + to_node
            if link_name in self.links:
                self.links[link_name].current_status = status

    def update_latency(self):
        """ Method makes a redis call to get latency for each link """
        print("Updating Latency Metrics...")
        rdb = redis.StrictRedis(host='10.10.4.252', port=6379, db=0)
        keys = rdb.keys()
        for key in keys:
            key = key.decode("utf-8")
            if "latency" in key:
                link_lat = rdb.lrange(key, 0, -1)[0]
                link_lat = json.loads(link_lat)
                link_lat = rdb.lrange(key, 0, -1)[0]
                link_lat = json.loads(link_lat)
                link_lat["from-router"] = str.title(link_lat["from-router"])
                link_lat["to-router"] = str.title(link_lat["to-router"])
                if link_lat["from-router"] == "New York":
                    link_lat["from-router"] = "NY"
                elif link_lat["from-router"] == "Los Angeles":
                    link_lat["from-router"] = "LA"
                elif link_lat["from-router"] == "San Francisco":
                    link_lat["from-router"] = "SF"
                if link_lat["to-router"] == "New York":
                    link_lat["to-router"] = "NY"
                elif link_lat["to-router"] == "Los Angeles":
                    link_lat["to-router"] = "LA"
                elif link_lat["to-router"] == "San Francisco":
                    link_lat["to-router"] = "SF"
                link_name = self.node_to_ip[
                    link_lat["from-router"]] + "_to_" + self.node_to_ip[link_lat["to-router"]]
                self.links[link_name].current_latency = link_lat[
                    "rtt-average(ms)"]


class TopologyNode():
    """ Class that repersents a node
        Attributes:
            name String
            Connections [] of sub class Links
    """

    def __init__(self, name, lat, longit, ip, connections):
        self.name = name
        self.ip_address = ip
        self.connections = connections
        self.latitude = lat
        self.longitude = longit

    def __str__(self):
        cons = ""
        for con in self.connections:
            cons = cons + con
        return "Node at: " + self.name + "Connects to " + cons

    def bugg_off_pylint(self):
        """ bugg off pylint
        """
        print("bugg off linter for ", self.name)


class TopologyLink():
    """ Class that repersents the Links belonging to a node
        Attributes:
            name
            fromNode
            toNode
            currentLatency
            currentStatus
    """

    def __init__(self, fromNode, from_int_ip, toNode, to_int_ip):
        self.name = fromNode + "_to_" + toNode
        self.from_node = fromNode
        self.to_node = toNode
        self.from_int_ip = from_int_ip
        self.to_int_ip = to_int_ip
        self.current_latency = 0
        self.current_status = str


class Connection():
    """
    Class repersents a pair of start and end nodes that will have LSPs.
    The Path is uni-directional. for bi-lateral paths there should be 2 objects A->B & B->A
    Class keeps attributes of the connection.

    Inputs:
        Topology
        start
        end
    """

    def __init__(self, topology, start, end):
        self.name = start + "_to_" + end
        self.start = start
        self.end = end
        self.gold_paths = {}
        self.silver_path = {}
        self.bronze_path = {}
        self.possible_paths = []
        paths = find_all_paths(topology.build_graph(), start, end)
        for path in paths:
            self.possible_paths.append(PossibleLSP(topology, path, start, end))
        topology.connections.update({self.name: self})

    def find_and_set_class_lsps(self):
        """
        Method to determine the Gold, Silver and Bronze class to-be updated LSP

        Gold One: The lowest Latency link.
                  Intended for real time applications
        Gold Two: The second lowest latency redundant link from gold One
                  Intended for real time and business critical applications
        Silver: The second lowest latency link that is not Gold Two
                Intended for business relevant applications
        Bronze: The third lowest latency link that is neither gold one, gold two or silver
                Intended for scavenger class applications
        """

        # Find Gold One
        def find_gold1(topo):
            relevant_latency = 99999
            for possible in topo.possible_paths:
                if possible.up_status == "Up":
                    if possible.total_latency < relevant_latency:
                        gold_one = possible
                        return gold_one

        def find_gold2(topo, gold_one):
            # Find Gold Two
            relevant_latency = 99999
            for possible2 in topo.possible_paths:
                links_in = []
                if possible2 != gold_one:
                    if possible2.up_status == "Up":
                        for indx, link in enumerate(possible2.links_in_path):
                            if link in gold_one.links_in_path:
                                links_in.append("yes")
                            else:
                                links_in.append("no")
                            reverse = link.split("_to_")
                            if reverse[1] + "_to_" + reverse[0] in gold_one.links_in_path:
                                links_in.append("yes")
                            else:
                                links_in.append("no")
                        if "yes" not in links_in:
                            if possible2.total_latency < relevant_latency:
                                gold_two = possible2
                                return gold_two

        def find_silver(topo, gold_one, gold_two):
            # Find Silver
            relevant_latency = 99999
            for possible3 in topo.possible_paths:
                if possible3 != gold_one:
                    if possible3 != gold_two:
                        if possible3.up_status == "Up":
                            if possible3.total_latency < relevant_latency:
                                silver = possible3
                                return silver

        def find_bronze(topo, gold_one, gold_two, silver):
            # Find Bronze
            relevant_latency = 99999
            for possible4 in self.possible_paths:
                if possible4 != gold_one:
                    if possible4 != gold_two:
                        if possible4 != silver:
                            if possible4.up_status == "Up":
                                if possible4.total_latency < relevant_latency:
                                    bronze = possible4
                                    return bronze
        gold_one = find_gold1(self)
        gold_two = find_gold2(self, gold_one)
        silver = find_silver(self, gold_one, gold_two)
        bronze = find_bronze(self, gold_one, gold_two, silver)

        # Updates the class values
        self.gold_paths = {"Gold_One": gold_one, "Gold_Two": gold_two}
        self.silver_path = silver
        self.bronze_path = bronze
        print("**********")
        print("Optimum LSPs Found for ", self.name, ": ")
        print("Gold 1 LSP:", gold_one.path)
        print("Gold 2 LSP:", gold_two.path)
        print("Silver LSP:", silver.path)
        print("Bronze LSP:", bronze.path)


class PossibleLSP():
    """ Class that repersents a possible LSP """

    def __init__(self, topology, path, start, end):
        self.topology = topology
        self.start = start
        self.end = end
        self.path = path
        self.hops_in_path = []
        self.links_in_path = []
        self.total_latency = 0
        self.hops = len(path) - 1
        self.up_status = ""
        self.ero_format = []
        for index, node in enumerate(path):
            if index < len(path) - 1:
                self.hops_in_path.append(topology.node_to_ip[node])
                l1nk = topology.node_to_ip[
                    node] + "_to_" + topology.node_to_ip[path[index + 1]]
                self.links_in_path.append(l1nk)
        for lnk in self.links_in_path:
            self.ero_format.append(
                {'topoObjectType': 'ipv4', 'address': topology.links[lnk].to_int_ip})

    def update_lsp_metrics(self):
        """Update this possible LSP metrics (status and latency) """
        latency_total = 0
        overall_status = "Up"
        for lnk in self.links_in_path:
            if lnk in self.topology.links:
                status = self.topology.links[lnk].current_status
                if status == "Down":
                    overall_status = "Down"
                latency_total = latency_total + \
                    self.topology.links[lnk].current_latency
            reverse = lnk.split("_to_")
            if reverse[1] + "_to_" + reverse[0] in self.topology.links:
                status = self.topology.links[
                    reverse[1] + "_to_" + reverse[0]].current_status
                if status == "Down":
                    overall_status = "Down"
                latency_total = latency_total + \
                    (self.topology.links[reverse[1] +
                                         "_to_" + reverse[0]]).current_latency
        self.total_latency = latency_total
        self.up_status = overall_status


def find_all_paths(graph, start, end, path=[]):
    """ Function that takes a graph, start and end as an input
        and returns all possible paths in the network
    """
    path = path + [start]
    if start == end:
        return [path]
    if start not in graph:
        return []
    paths = []
    for node in graph[start]:
        if node not in path:
            newpaths = find_all_paths(graph, node, end, path)
            for newpath in newpaths:
                paths.append(newpath)
    return paths

def ping_vms():
    """Ping the VM from NY -> SF & SF -> NY """
    SF_ip = "10.10.2.225"
    NY_ip = "10.10.2.205"
    uname = "group-six"
    password = "Group-Six"
    #Change below to test
    SF_cmd = 'ping -c2 10.10.2.205'
    NY_cmd = 'ping -c2 10.10.2.225'
    SF_conn_obj = PingTest(SF_ip, uname, password)
    SF_conn_obj.callSF(SF_cmd)
    NY_conn_obj = PingTest(NY_ip, uname, password)
    NY_conn_obj.callNY(NY_cmd)

def graph_statis(data, place, interface):
    """
    rlange key start stop. return element of list stored at key.

    start and stop 0 based index. 0-->1 -1--> last

    chicago:ge_1/0/5:traffic statistics
    """
    r = redis.StrictRedis(host='10.10.4.252', port=6379, db=0)

    datainterface = r.lrange(data, 0, -1)

    #print chi_ge_105[0]
    data = json.loads(datainterface[0])
    time = []
    input_data = []
    output_data = []
    for i in range(len(datainterface)):
        data = json.loads(datainterface[i])
        time.append(data['timestamp'][0:6])
        input_data.append(int(data['stats'][0]['input-bytes'][0]['data']))
        output_data.append(int(data['stats'][0]['output-bytes'][0]['data']))

    df = pd.DataFrame([time, input_data, output_data]).T
    df.columns = ['Time', 'Input_Data', 'Output_Data']

    dd = df.groupby('Time').sum().reset_index()
    #rank the group based on time
    #reduce the first and last hour because the data is not completed for one hour
    dd = dd[-16:-1].reset_index()
#    dd.drop(df.columns['Index', axis=1)  # df.columns is zero-based pd.Index
    #Tranfer the byte unit to corresponding unit
    InputUnit = 'Byte'
    if(min(dd['Input_Data']) > np.power(2,20)):
        if(min(dd['Input_Data']) > np.power(2,30)):
            if(min(dd['Input_Data'])/1024 > np.power(2,30)):
                 dd['Input_Data'] /= 1024
                 dd['Input_Data'] /= np.power(2,30)
                 InputUnit = 'TB'
            else:
                dd['Input_Data'] /=  np.power(2,30)
                InputUnit = 'GB'
        else:
            dd['Input_Data'] /= np.power(2,20)
            InputUnit = 'MB'
    else:
        dd['Input_Data'] /= np.power(2,10)
        InputUnit = 'KB'
#    print InputUnit
    OutputUnit = 'Byte'
    if(min(dd['Output_Data']) > np.power(2,20)):
        if(min(dd['Output_Data']) > np.power(2,30)):
            if(min(dd['Output_Data'])/1024 > np.power(2,30)):
                 dd['Output_Data'] /= 1024
                 dd['Output_Data'] /= np.power(2,30)
                 OutputUnit = 'TB'
            else:
                dd['Output_Data'] /=  np.power(2,30)
                OutputUnit = 'GB'
        else:
            dd['Output_Data'] /= np.power(2,20)
            OutputUnit = 'MB'
    else:
        dd['Input_Data'] /= np.power(2,10)
        OutputUnit = 'KB'
#    print OutputUnit
#    print dd
#

    Xaxis = range(len(dd.axes[0]))
    Xlabel = dd['Time']

    plt.subplot(211)
    plt.bar(Xaxis, dd['Input_Data'], width = 0.4, label = 'Input Data Per Hour',color = 'green')
    plt.xticks(Xaxis, Xlabel, fontsize = 8)
    plt.ylabel("Input_Data " + '(' + InputUnit + ')')
    plt.grid()
    low = min(dd['Input_Data'])
    high =  max(dd['Input_Data'])
    plt.ylim(low-(high-low), high+(high-low))
#    myLocator = mticker.MultipleLocator(4)
#    plt.subplot(211).xaxis.set_major_locator(myLocator)

    plt.subplot(212)
    plt.bar(Xaxis,dd['Output_Data'], width = 0.4, label = 'Input Data Per Hour', color = 'orange')
    plt.xticks(Xaxis, Xlabel, fontsize = 8)
    plt.xlabel('Time' + ' (Place: ' + place +' Interface: ' + interface +')')
    plt.ylabel("Output_Data " + '(' + OutputUnit + ')')
    low2 = min(dd['Output_Data'])
    high2 =  max(dd['Output_Data'])
    plt.grid()
    plt.ylim(low2-(high-low), high2+(high-low))
    plt.show()
    pause(20)

def graph_hop():
    """Graphs the hop counts in a bar chart """
    #http://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1/te-lsps
    #load the data
    url = "https://10.10.2.29:8443/oauth2/token"
    payload = {'grant_type': 'password', 'username': 'group6', 'password': 'Group6'}
    response = requests.post (url, data=payload, auth=('group6','Group6'), verify=False)
    json_data = json.loads(response.text)
    authHeader= {"Authorization":"{token_type} {access_token}".format(**json_data)}

    r = requests.get('https://10.10.2.29:8443/NorthStar/API/v1/tenant/1/topology/1/te-lsps/', headers=authHeader, verify=False)
    p = json.dumps(r.json())
    lsp_list = json.loads(p)

    # Target LSP
    list = ['GROUP_SIX_NY_SF_LSP1', 'GROUP_SIX_NY_SF_LSP2', 'GROUP_SIX_NY_SF_LSP3', 'GROUP_SIX_NY_SF_LSP4',
            'GROUP_SIX_SF_NY_LSP1', 'GROUP_SIX_SF_NY_LSP2', 'GROUP_SIX_SF_NY_LSP3', 'GROUP_SIX_SF_NY_LSP4']
    # create two lists to hold information for lsp and number of hop
    hopcount = []
    list2 =[]

    i = 0
    #compare the 88 lsps with our target 8 lsp list
    #if find it, break, and return the number of hop
    while(i < len(list)):
        for lsp in lsp_list:
            if lsp['name'] == list[i]:
                list2.append(lsp['name'][10:20])
                break
#        print (json.dumps(lsp, indent=4, separators=(',', ': ')))
#        print (lsp['liveProperties']['rro'])
        count = 1
        for nhop in lsp['liveProperties']['rro']:
#            print ('hop' + str(count) + ':', nhop['address'])
            count = count + 1
        hopcount.append(count-1)
        i = i + 1
    #use pandas create a datafram to include the info for both lsp location and number of hops
    df = pd.DataFrame([list2, hopcount]).T
    df.columns = ['LSP', 'NumberofHop']
    #print (df)

    #Graph the number of hop for 8 different LSPs
    Xaxis = range(len(list))
    Xlabel = df['LSP']
    plt.bar(Xaxis,df['NumberofHop'], width = 0.4, color = 'green')
    plt.xticks(Xaxis,Xlabel,fontsize = 8)
    plt.xlabel("LSP")
    plt.ylabel("Number of Hops")
    pause(10)



if __name__ == "__main__":
    TOPO = Topology("10.10.2.29", "group6", "Group6")
    # TOPO.listen_and_respond_to_link_events()
    print("\n\n\n*****************************************")
    print("Welcome to the MPLS Optimizer developed by 14203 Broncos \nfor the 2017 OpenLab SDN Throwdown")
    print("This application dynamically responds to topology changes \nand ensures that the lowest latency redundant links are always provisioned for a customer LSP\n")
    print("+-+-+-+-+-+-+-+ +-+-+ +-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+\n")
    print("|P|o|w|e|r|e|d| |b|y| |J|u|n|i|p|e|r| |O|p|e|n|L|a|b|\n")
    print("+-+-+-+-+-+-+-+ +-+-+ +-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+\n \n \n")
    print("""                                                   .----.
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
    """)

    input_cmd = "start"
    while input_cmd != "exit":
        input_cmd = input('Enter a command or ? for help: ')
        if input_cmd == "?":
            print("\nCommand not found")
            print("\nAvailable Commands:")
            print("*******************")
            print("Action Commands")
            print("*******************")
            print("start responsive")
            print("topology reconverge")
            print("ping VMs")
            print("\n*******************")
            print("Show Commands")
            print("*******************")
            print("show nodes")
            print("show links")
            print("show links latency")
            print("show links status")
            print("show current lsp")
            print("show node interface names")
            print("\n*******************")
            print("Graph Commands")
            print("*******************")
            print("graph hops")
            print("graph interface utilization *node* *interface*")
            print("\n*******************")
            print("Documentation Commands")
            print("*******************")
            print("view documentation")
        elif input_cmd == "topology reconverge":
            TOPO.converge_and_apply_lsp()
        elif input_cmd == "show nodes":
            for node in TOPO.nodes:
                print(node)
        elif input_cmd == "show links":
            for link in TOPO.links:
                print(link)
        elif input_cmd == "show links latency":
            for link in TOPO.links:
                print(TOPO.ip_to_node[TOPO.links[link].from_node], " to ", TOPO.ip_to_node[TOPO.links[link].to_node], ": ", TOPO.links[link].current_latency)
        elif input_cmd == "show links status":
            for link in TOPO.links:
                if TOPO.links[link].current_status == "Up" or TOPO.links[link].current_status == "Down":
                    print(TOPO.ip_to_node[TOPO.links[link].from_node], " to ", TOPO.ip_to_node[TOPO.links[link].to_node], ": ", TOPO.links[link].current_status)
        elif input_cmd == "show current lsp":
            for conn in TOPO.connections:
                print("\nLSP for Connection ", TOPO.connections[conn].start, " To ", TOPO.connections[conn].end)
                print("Gold One: ", TOPO.connections[conn].gold_paths["Gold_One"].path)
                #print("     Latency: ", TOPO.connections[conn].gold_paths["Gold_One"].total_latency, "Hops: ", TOPO.connections[conn].gold_paths["Gold_One"].hops)
                print("Gold Two: ", TOPO.connections[conn].gold_paths["Gold_Two"].path)
                #print("     Latency: ", TOPO.connections[conn].gold_paths["Gold_One"].total_latency, "Hops: ", TOPO.connections[conn].gold_paths["Gold_Two"].hops)
                print("Silver: ", TOPO.connections[conn].silver_path.path)
                #print("     Latency: ", TOPO.connections[conn].silver_path.total_latency,"Hops: ", TOPO.connections[conn].silver_path.hops)
                print("Bronze: ", TOPO.connections[conn].bronze_path.path)
                #print("     Latency: ", TOPO.connections[conn].silver_path.total_latency,"Hops: ", TOPO.connections[conn].bronze_path.hops)
                print("*******************\n")

        elif input_cmd == "view documentation":
            url = 'file:///Users/branblac/Documents/Dev/openlab/_build/html/index.html#module-link_class'
            webbrowser.open(url)
        elif input_cmd == "start responsive":
            thread = threading.Thread(target=TOPO.listen_and_respond_to_link_events)
            thread.start()
        elif input_cmd == "graph hops":
            graph_hop()
        elif input_cmd == "show node interface names":
            print("""
            NY
            ge-1/0/3
            ge-1/0/5
            ge-1/0/7

            Miami
            ge-1/0/0
            ge-1/0/1
            ge-1/0/2
            ge-1/0/3
            ge-1/0/4

            Tampa
            ge-1/0/0
            ge-1/0/1
            ge-1/0/2

            Chicago
            ge-1/0/1
            ge-1/0/2
            ge-1/0/3
            ge-1/0/4

            Dallas
            ge-1/0/0
            ge-1/0/1
            ge-1/0/2
            ge-1/0/3
            ge-1/0/4

            Houston
            ge-1/0/0
            ge-1/0/1
            ge-1/0/2
            ge-1/0/3

            LA
            ge-1/0/0
            ge-1/0/1
            ge-1/0/2

            SF
            ge-1/0/0
            ge-1/0/1
            ge-1/0/3
            """)
        elif "graph interface utilization" in input_cmd:
            words = input_cmd.split(" ")
            try:
                print("hit ctrl+C to exit graph")
                node = words[3]
                interface = words[4]
                graph_thread = threading.Thread(target=graph_statis(node + ":" + interface + ":traffic statistics", node, interface))
                graph_thread.start()
            except(KeyboardInterrupt):
                print("Exiting Graph")
            except:
                print("error with node and interface entry, try again")
        elif input_cmd == "ping VMs":
            ping_vms()
        else:
            print("\nCommand not found")
            print("\nAvailable Commands:")
            print("\n*******************")
            print("Action Commands")
            print("*******************")
            print("start responsive")
            print("topology reconverge")
            print("ping VMs")
            print("\n*******************")
            print("Show Commands")
            print("*******************")
            print("show nodes")
            print("show links")
            print("show links latency")
            print("show links status")
            print("show current lsp")
            print("show node interface names")
            print("\n*******************")
            print("Graph Commands")
            print("*******************")
            print("graph hops")
            print("graph interface utilization *node* *interface*")
            print("\n*******************")
            print("Documentation Commands")
            print("*******************")
            print("view documentation")
