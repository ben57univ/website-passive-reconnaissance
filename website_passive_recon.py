# -*- coding: utf-8 -*-
"""
Script to automate, when possible, the passive reconnaissance performed a website prior to an assessment.
Also used to guide the reconnaissance phase by defining all steps (manual or automated).

Dependencies:
pip install colorama dnspython shodan requests

API Key INI file example (ex: api_key.ini):
[API_KEYS]
shodan = xxx    
"""
import colorama
import argparse
import configparser
import dns.resolver
import requests
import shodan
import time
import datetime
from termcolor import colored
from dns.resolver import NoAnswer

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:70.0) Gecko/20100101 Firefox/70.0"

def print_infos(info_list, prefix=""):
    for info in info_list:
        print(f"{prefix}{info}")


def get_ip_addresses(domain, name_server, record_types):
    ips = []
    resolver = dns.resolver.Resolver(configure=True)
    if name_server is not None:
        resolver.nameservers = [name_server]
    for record_type in record_types:
        try:
            answer = resolver.query(domain, record_type)
            for data in answer:
                ips.append(data.to_text())
        except NoAnswer:
            pass
    return ips


def get_cnames(domain, name_server):
    cnames = []
    resolver = dns.resolver.Resolver(configure=True)
    if name_server is not None:
        resolver.nameservers = [name_server]
    try:
        answer = resolver.query(domain, "CNAME")
        for data in answer:
            cnames.append(data.target.to_text())
    except NoAnswer:
        pass
    return cnames


def get_shared_hosts(ip):
    infos = []
    service_url = f"https://api.hackertarget.com/reverseiplookup/?q={ip}"
    response = requests.get(service_url, headers={"User-Agent": f"User-Agent: {USER_AGENT}"})
    vhosts = response.text
    for vhost in vhosts.splitlines():
        if vhost != ip:
            infos.append(vhost)
    return infos


def get_ip_owner(ip):
    infos = []
    service_url = f"https://rest.db.ripe.net/search.json?query-string={ip}&flags=no-referenced&flags=no-irt&source=RIPE"
    response = requests.get(service_url, headers={"User-Agent": f"User-Agent: {USER_AGENT}"})
    data = response.json()
    properties = data["objects"]["object"][0]["attributes"]["attribute"]
    for property in properties:
        if "name" in property:
            name = property["name"]
            value = property["value"]
            infos.append(f"{name} = {value}")
    return infos


def get_shodan_ip_infos(ip, api_key):
    infos = []
    api = shodan.Shodan(api_key)
    data = api.host(ip, minify=True)
    value = data["last_update"]
    infos.append(f"Last update = {value}")
    value = data["isp"]
    infos.append(f"ISP = {value}")
    value = data["org"]
    infos.append(f"Organization = {value}")
    value = " , ".join(data["hostnames"])
    infos.append(f"Hostnames = {value}")
    value = data["ports"]
    infos.append(f"Ports = {value}")
    return infos


def get_qualys_sslscan_cached_infos(domain, ip):
    infos = []
    service_url = f"https://api.ssllabs.com/api/v3/getEndpointData?host={domain}&s={ip}&fromCache=on"
    response = requests.get(service_url, headers={"User-Agent": f"User-Agent: {USER_AGENT}"})
    data = response.json()
    if "errors" in data:
        error_msg = ""
        for error in data["errors"]:
            error_msg += error["message"]
        infos.append(f"Error = {error_msg}")   
    if "statusMessage" in data and data["statusMessage"] == "Ready":
        if "ipAddress" in data:
            value = data["ipAddress"]
            infos.append(f"IPAddress = {value}")   
        if "serverName" in data:
            value = data["serverName"]
            infos.append(f"ServerName = {value}")   
        if "grade" in data:
            value = data["grade"]
            infos.append(f"Grade = {value}")   
        if "details" in data:
            details = data["details"]
            value = datetime.datetime.fromtimestamp(details["hostStartTime"]/1000.0).strftime("%Y-%d-%mT%H:%M:%S")
            infos.append(f"AssessmentStartingTime = {value}")                           
            value = details["vulnBeast"]
            infos.append(f"BEAST = {value}")      
            value = details["heartbleed"]
            infos.append(f"HEARTBLEED = {value}")             
            value = details["poodle"]       
            infos.append(f"POODLE = {value}")           
            value = details["freak"]        
            infos.append(f"FREAK = {value}")                 
            value = details["logjam"]        
            infos.append(f"LOGJAM = {value}")  
            value = details["drownVulnerable"]        
            infos.append(f"DROWN = {value}")          
            value = (details["ticketbleed"] == 2)
            infos.append(f"TICKETBLEED = {value}")           
            value = (details["bleichenbacher"] == 2 or details["bleichenbacher"] == 3)
            infos.append(f"ROBOT = {value}")           
    return infos                        


if __name__ == "__main__":
    colorama.init()
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", action="store", dest="domain_name", help="Domain to analyse (ex: www.righettod.eu).", required=True)
    parser.add_argument("-a", action="store", dest="api_key_file", default=None, help="Configuration INI file with all API keys (ex: conf.ini).", required=False)
    parser.add_argument("-n", action="store", dest="name_server", default=None, help="Name server to use for the DNS query (ex: 8.8.8.8).", required=False)
    args = parser.parse_args()
    api_key_config = configparser.ConfigParser()
    api_key_config["API_KEYS"] = {}
    print(colored(f"##############################################", "green", attrs=["bold"]))
    print(colored(f"### TARGET: {args.domain_name.upper()}", "green", attrs=["bold"]))
    print(colored(f"##############################################", "green", attrs=["bold"]))
    print(colored(f".::Starting reconnaissance::.", "white", attrs=["bold"]))
    if args.api_key_file is not None:
        api_key_config.read(args.api_key_file)
        print(colored(f"[CONF] API key file '{args.api_key_file}' loaded.", "green", attrs=["bold"]))
    if args.name_server is not None:
        print(colored(f"[CONF] Name server {args.name_server} used for all DNS query.", "green", attrs=["bold"]))
    else:
        print(colored(f"[CONF] System default name server used for all DNS query.", "green", attrs=["bold"]))
    print(colored(f"[DNS] Extract the IP V4/V6 addresses...","blue", attrs=["bold"]))
    ips = get_ip_addresses(args.domain_name, args.name_server, ["A", "AAAA"])
    print_infos(ips)
    print(colored(f"[DNS] Extract the aliases...", "blue", attrs=["bold"]))
    cnames = get_cnames(args.domain_name, args.name_server)
    print_infos(cnames)
    print(colored(f"[RIPE] Extract the owner information of the IP addresses...", "blue", attrs=["bold"]))
    for ip in ips:
        print(colored(f"{ip}", "yellow", attrs=["bold"]))
        informations = get_ip_owner(ip)
        print_infos(informations, "  ")
    print(colored(f"[SHODAN] Extract the information of the IP addresses and domain...", "blue", attrs=["bold"]))
    if "shodan" in api_key_config["API_KEYS"]:
        api_key = api_key_config["API_KEYS"]["shodan"]
        print(colored(f"{args.domain_name}", "yellow", attrs=["bold"]))
        print("  Search with filter using the API with a free tier API key is not allowed, so, use the following URL from a browser:")
        print(f"  https://www.shodan.io/search?query=hostname%3A{args.domain_name}")
        is_single_ip = len(ips) < 2
        for ip in ips:
            print(colored(f"{ip}", "yellow", attrs=["bold"]))
            informations = get_shodan_ip_infos(ip, api_key)
            print_infos(informations, "  ")
            # Add tempo due to API limitation (API methods are rate-limited to 1 request/ second)
            if not is_single_ip:
                time.sleep(1)
    else:
        print(colored(f"Skipped because no API key file was specified!","red", attrs=["bold"]))
    print(colored(f"[HACKERTARGET] Extract hosts shared by each IP address...", "blue", attrs=["bold"]))
    for ip in ips:
        print(colored(f"{ip}", "yellow", attrs=["bold"]))
        informations = get_shared_hosts(ip)
        print_infos(informations, "  ")
    print(colored(f"[NETCRAFT] Provide the URL to report for the domain and IP addresses...", "blue", attrs=["bold"]))
    print("No API provided and browser required, so, use the following URL from a browser:")
    print(f"  https://toolbar.netcraft.com/site_report?url={args.domain_name}")
    for ip in ips:
        print(f"  https://toolbar.netcraft.com/site_report?url={ip}")
    print(colored(f"[GOOGLE] Provide the URL for dork for the domain...", "blue", attrs=["bold"]))
    print("Use the following URL from a browser:")
    print(f"  https://www.google.com/search?q=site%3A{args.domain_name}&oq=site%3A{args.domain_name}",)
    print(colored(f"[QUALYS] Extract information from SSL cached scan for the domain and IP addresses...", "blue", attrs=["bold"]))
    for ip in ips:
        print(colored(f"{ip}", "yellow", attrs=["bold"]))
        informations = get_qualys_sslscan_cached_infos(args.domain_name, ip)
        print_infos(informations, "  ")
    print(colored(f".::Reconnaissance finished::.", "white", attrs=["bold"]))