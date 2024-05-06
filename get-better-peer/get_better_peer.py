#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, pickle, glob, re, json
import numpy as np
import pandas as pd
import copy
import time

from pathlib import Path
from collections import Counter
from tqdm import tqdm
import argparse

from ping3 import ping
import toml, requests
import socket

import logging
from datetime import datetime, timezone, timedelta
import pytz
def timetz(*args):    return datetime.now(tz).timetuple()

logger = logging.getLogger()
tz = pytz.timezone('Asia/Seoul') # UTC, Asia/Seoul, Europe/Berlin
logging.Formatter.converter = timetz
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', datefmt = '%Y-%m-%d %H:%M:%S', level=logging.INFO)

def get_location(addr: str):
  ip_address = socket.gethostbyname(addr)
  time.sleep(10)
  response = requests.get(f'https://ipapi.co/{ip_address}/json/').json()
  return [response.get("country_name"), response.get("region"), response.get("city"), response.get("latitude"), response.get("longitude")]

def get_ping(addr: str):
  try:
    result = ping(addr, unit='ms')
    if result == None:
        return 0
    else:
        return np.round(result, 3)
  except Exception as e:
    return 0

## get a nearest distance on the Earth surface by Haver-Sine Equation
def haversine(Olat,Olon, Dlat,Dlon):
  radius = 6371.  # km

  d_lat = np.radians(Dlat - Olat)
  d_lon = np.radians(Dlon - Olon)
  a = (np.sin(d_lat / 2.) * np.sin(d_lat / 2.) + np.cos(np.radians(Olat)) * np.cos(np.radians(Dlat)) * np.sin(d_lon / 2.) * np.sin(d_lon / 2.))
  c = 2. * np.arctan2(np.sqrt(a), np.sqrt(1. - a))
  d = radius * c
  return d

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--config", action='store', type=str, default="./config.toml", help="configuration file location")
  parser.add_argument("--base", action='store', type=str, choices=['distance', 'latency'], default="distance", help="logical selection : distance(default)/latency")
  parser.add_argument("--take", action='store', type=int, default="5", help="Number of place to take for peers")
  
  args = parser.parse_args()

  config = toml.load(Path(args.config).absolute())

  ip4_pattern = r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'
  is_ip4 = lambda x : re.match(ip4_pattern, x) != None

  ## get the local machine's public ip
  my_ip = requests.get("https://api.ipify.org").text
  logger.info(f"My machine public IP address : {my_ip}")

  tqdm.pandas()

  ## get the proper rpc connection
  ress = []
  for addr in config['info']['rpc_list']:
    try:
      res = requests.get(f'{addr}/net_info')
    except Exception as e:
      logger.info(f"{addr} is unreachable. The reason is {e}")
    
    if res != None:
      ress.append(res)

  if len(ress) == 0:
    logger.info("There is no possible connection on the rpc server list")
    exit(1)
  
  ## get a full list of connected peer list on the rpcs
  temp = []
  for s in ress:
    if s.status_code != 200:
      continue
    t = pd.DataFrame.from_dict(json.loads(s.text)['result']['peers']).iloc[:, [0,3]]
    t = t[t.iloc[:, 1].apply(is_ip4)]
    temp.append(t)
  temp = pd.concat(temp, axis=0).drop_duplicates('remote_ip').reset_index(drop=True)

  ## get the infos(region, distance, latency and so on)
  origin = get_location(my_ip)
  logger.info(f"My machine is in {origin[1]}, {origin[0]}")

  locations = pd.DataFrame(temp.iloc[:, 1].progress_apply(lambda x : get_location(x)).tolist())
  locations['distance'] = locations.progress_apply(lambda x: haversine(origin[-2], origin[-1], x[3], x[4]), axis=1)


  result = pd.concat([temp.iloc[:, 1],                              ##ip
                      locations,                                    ## region infos
                      temp.iloc[:, 1].progress_apply(lambda x: get_ping(x)), ## latency
                      pd.concat([pd.concat([temp.iloc[:, 0].apply(lambda x: re.split(':', x['id'])[-1]),temp.iloc[:, 1]], axis=1).progress_apply(lambda x: '@'.join(x), axis=1)
                                           ,temp.iloc[:, 0].apply(lambda x: re.split(':', x['listen_addr'])[-1])], axis=1).progress_apply(lambda x: ':'.join(x), axis=1)], ## peer_list
                                           axis=1, ignore_index=True)
  logger.info(f"# of result : {len(result)}")
  result.columns = ['ip_address', 'country', 'region', 'city', 'latitude', 'longitude', 'distance', 'latency', 'peer_address']
  
  ## get better peers by election logic
  is_valid = lambda x : not (x[1] != 0 and x[2] == 0 )  ## if distance exists, latency should not be zero
  elected = result[['region', 'distance','latency','peer_address']].groupby('region').agg({'distance':np.mean, 'latency':max, 'peer_address':list}).sort_values('latency').reset_index()
  elected.to_csv(config['info']['chain_name'] + '_result.csv', index=False)

  logger.info(f"peer will be sorted by {args.base}")
  elected = elected.sort_values(args.base).reset_index(drop=True)
  # elected = elected[elected.apply(lambda x : is_valid(x), axis=1)].reset_index(drop=True)
  logger.info(f"# of distance groups is {len(elected) - 1}")

  ## save the result
  elected.to_csv(config['info']['chain_name'] + '_result.csv', index=False)
  
  filename = Path.joinpath(Path('.'), config['info']['chain_name'] + "_persistent_peers.txt").absolute()
  elected_list = [item for sublist in elected[elected.apply(lambda x : is_valid(x), axis=1)].iloc[:args.take, -1].tolist() for item in sublist]
  logger.info(f"# of elected peers is {len(elected_list)}")
  with open(filename, 'w') as p_list:
    p_list.writelines("%s\n" % ','.join(elected_list))
  logger.info(f"better peers in {filename}")