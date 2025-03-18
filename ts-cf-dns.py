#!/usr/bin/env python3
# Script to grab the ULA IPv6 addresses from TailScale and shove them into other systems
# such as cloudflare using the API, bind, or pihole.
# It should be noted that putting ULA (or any private addressing) into public DNS is stupid
# The downsides of which are well traveled, well studued, and generally just stupid.
# This only supports IPv6 because there is no reason to support legacy IPv4 when everything on the tailnet  
# has a valid IPv6 address, and when dual-stacked the IPv6 ULA will never be used (without rfc6724-update)

import requests
import json
import argparse

# Configuration
TAILSCALE_API_KEY = "your_tailscale_api_key" # required
TAILSCALE_TAILNET = "your_tailnet" # required
CLOUDFLARE_API_KEY = "your_cloudflare_api_key" # required if using cloudflare, duh
CLOUDFLARE_ZONE_ID = "your_cloudflare_zone_id" # required if using cloudflare
CLOUDFLARE_EMAIL = "your_email" # required if using cloudflare
DNS_DOMAIN = "example.com"  # Base domain for DNS records, required

def get_tailscale_ips():
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILSCALE_TAILNET}/devices"
    headers = {
        "Authorization": f"Basic {TAILSCALE_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    devices = response.json()["devices"]
    
    ipv6_addresses = {
        device["hostname"]: next((ip for ip in device["addresses"] if ":" in ip), None)
        for device in devices
    }
    return {host: ip for host, ip in ipv6_addresses.items() if ip is not None}

def update_cloudflare_dns(hostname, ipv6):
    dns_name = f"{hostname}.{DNS_DOMAIN}"
    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Check if the record already exists
    params = {"type": "AAAA", "name": dns_name}
    existing_records = requests.get(url, headers=headers, params=params).json()
    
    if existing_records["success"] and existing_records["result"]:
        record_id = existing_records["result"][0]["id"]
        update_url = f"{url}/{record_id}"
        data = {"type": "AAAA", "name": dns_name, "content": ipv6, "ttl": 1, "proxied": False}
        response = requests.put(update_url, headers=headers, json=data)
    else:
        data = {"type": "AAAA", "name": dns_name, "content": ipv6, "ttl": 1, "proxied": False}
        response = requests.post(url, headers=headers, json=data)
    
    return response.json()

def format_bind(ipv6_records):
    return "\n".join(f"{hostname}. IN AAAA {ipv6}" for hostname, ipv6 in ipv6_records.items())

def format_pihole(ipv6_records):
    return "\n".join(f"{ipv6} {hostname}.{DNS_DOMAIN}" for hostname, ipv6 in ipv6_records.items())

def main():
    parser = argparse.ArgumentParser(description="Tailscale to Cloudflare DNS Updater")
    parser.add_argument("-c", action="store_true", help="Perform Cloudflare migration")
    parser.add_argument("-b", action="store_true", help="Format output as BIND zone file")
    parser.add_argument("-p", action="store_true", help="Format output as Pi-hole local.list format")
    parser.add_argument("-o", type=str, help="Output to a named file")
    args = parser.parse_args()
    
    ipv6_records = get_tailscale_ips()
    output = ""
    
    if args.c:
        for hostname, ipv6 in ipv6_records.items():
            result = update_cloudflare_dns(hostname, ipv6)
            print(f"Updated {hostname}: {result}")
    
    if args.b:
        output = format_bind(ipv6_records)
    elif args.p:
        output = format_pihole(ipv6_records)
    
    if args.o:
        with open(args.o, "w") as f:
            f.write(output)
    else:
        print(output)

if __name__ == "__main__":
    main()
