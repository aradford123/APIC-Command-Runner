#!/usr/bin/env python

import os, sys
import ast
from  login import login
import json
import jtextfsm as textfsm

from argparse import ArgumentParser

def run_command(apic, devs, cmds):

    if cmds is [None]:
        cmds =["show clock"]
    print (cmds)

    dto={
                    "name" : "show ver",
                    "deviceUuids" : devs,
                    "commands" : cmds
                }
    task = apic.networkdevicepollercli.submitCommands(commandRunnerDto=dto)
    if task:

        task_response=apic.task_util.wait_for_task_complete(task, timeout=10)
        if task_response:
            # only needed until we fix the output of this progress field to be json
            fileId=ast.literal_eval(task_response.progress)['fileId']
            file = apic.file.downLoadFile(fileId=fileId)
            return file.text

def deviceip_to_id(apic, device_ip):
    network_device = apic.networkdevice.getNetworkDeviceByIp(ipAddress=device_ip)
    return network_device.response.id

def deviceid_to_ip(apic, deviceId):
    network_device = apic.networkdevice.getNetworkDeviceById(id=deviceId)
    return network_device.response.managementIpAddress

def deviceid_to_name(apic, deviceId):
    network_device = apic.networkdevice.getNetworkDeviceById(id=deviceId)
    return network_device.response.hostname


def tag_to_ip(apic, tag):
    if tag is None:
        return []
    topology = apic.topology.getPhysicalTopology()
    return [ node.ip for node in topology.response.nodes if node.tags and tag in node.tags]

def format_response(apic, res_json, human, fsm):
    if human:
        for response in res_json:
            success = response['commandResponses']['SUCCESS']
            failure = response['commandResponses']['FAILURE']
            devuuid = response["deviceUuid"]
            for key in success.keys():
                print ('{ip}: {command}:\n{success}\n{failure}'.format(ip=deviceid_to_ip(apic, devuuid),
                                                               command=key, success=success[key],
                                                     failure=failure))
    elif fsm:
        # need to generate this in an optimal way
        # could have more than one command
        # should fail if this does not work?
        template = open(fsm)
        re_table = textfsm.TextFSM(template)
        table_keys = re_table.header
        for response in res_json:
            re_table.Reset()
            success = response['commandResponses']['SUCCESS']
            failure = response['commandResponses']['FAILURE']
            devuuid = response["deviceUuid"]
            for key in success.keys():
                if success:
                    raw = re_table.ParseText(success[key])
                    formatted = ":".join([":".join([x+":"+y for (x,y) in zip(table_keys,record)]) for record in raw])

                    print('{ip}:{name}:{command}:{success}'.
                       format(ip=deviceid_to_ip(apic, devuuid),
                              name=deviceid_to_name(apic, devuuid),
                              command=key, success=formatted))
                if failure:
                     print('{ip}:{command}:FAILURE {failure}'.
                           format(ip=deviceid_to_ip(apic, devuuid),
                               command=key,
                               failure=failure))

    else:
        print(json.dumps(res_json, indent=2))

if __name__ == "__main__":
    parser = ArgumentParser(description='Select options.')

    parser.add_argument('--commands', type=str,
                        help="commands to run")
    parser.add_argument('--intregexp', type=str,
                        help="interface regular expression (requires a {{INTF}} parameter in the command")
    parser.add_argument('--tag', type=str,
                        help="tag for devices to choose")
    parser.add_argument('--ip', type=str,
                       help="ip address for devices to choose")
    parser.add_argument('--human', action='store_true',
                        help="human output or machine")
    parser.add_argument('--fsm', action='store_true',
                        help="format output using textfsm template")
    parser.add_argument('-v', action='store_true',
                        help="verbose")
    args = parser.parse_args()
    apic = login()
    print ("tag:", args.tag)
    ips = None
    if args.tag:
        ips = tag_to_ip(apic, args.tag)

    elif args.ip:
        ips = [args.ip]

    if ips:
        ids = [deviceip_to_id(apic, ip) for ip in ips]
    else:
        print("no ips or tags for network devices")
        validCmds = apic.networkdevicepollercli.getLegitCliKeywords()
        print("ValidCommands: {0}".format(", ".join(validCmds.response)))
        exit(1)
    #print ("commands:", args.commands)
    try:
        cmds = json.loads(args.commands)
    except ValueError:
        cmds = [args.commands]

    fsm = args.fsm
    if args.fsm:
        file="fsm/" + '_'.join(args.commands.split()) + '.textfsm'
        try:
            f = open(file)
            f.close()
        except KeyError:
            print("no fsm file", file)
            exit(1)
        fsm = file

    res = run_command(apic, devs=ids, cmds=cmds)
    res_json = json.loads(res)
    format_response(apic, res_json, args.human, fsm)



# max of 5 commands per request