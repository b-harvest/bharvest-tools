# This is for get a great and better peer from your own validator node.

## prerequisite

- python 3.6 or later
- install the dependencies

```bash
# check the python and pip version
which python3

python3 --version
pip3 --version

cd vo-tools/general-tools/get-better-peer

## install dependencies
python3 -m pip install -r requirements.txt
```

## config-example.toml

- edit the rpc servers on the list

```bash
cp config-example.toml config.toml

vi config.toml
```

- chain_name : chain name (will be filename prefix on result)
- rpc_list   : rpc server list you want to connect. ex) ["https://rpc-bandchain-ia.cosmosia.notional.ventures:443", "https://band-rpc.ibs.team:443", "http://rpc.laozi1.bandchain.org:80"]

## how to run

```bssh
cd vo-tools/general-tools/get-better-peer
python3 get_better_peer.py --config config-example.toml \
                           --base 'distance' \            # 'distance' or 'latency'
                           --take 5                       # Number of peer group to take
```

## How to utilize
- Whole list is in "<CHAIN_NAME>_result.csv"
- header will be "region,distance,latency,peer_address"
- The nice persistent peer list will be in "<CHAIN_NAME>_persistent_peers.txt"

## usage

```bash
PEERS=`cat <CHAIN_NAME>_persistent_peers.txt`
sed -i.bak -e "s/^persistent_peers *=.*/persistent_peers = \"$PEERS\"/" ${CHAIN_CONFIG_LOCATION}/config.toml
```