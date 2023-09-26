# Bittensor (Vicuna) Miner Setup Guide

This guide provides detailed instructions for setting up and running a Bittensor Vicuna miner using the text-prompting repository.

## Prerequisites
Before you begin, ensure that you have PM2 installed to manage your processes. If you don’t have it installed, follow the installation guide [here](https://pm2.io/docs/runtime/guide/installation/).

## 1. Install the text-prompting Repository
To start, install the text-prompting repository. Navigate to the directory where you’ve cloned or downloaded `text_prompting`, and run the following command:

```sh
python -m pip install -e ~/text_prompting
```

## 2. Install Specific Miner Requirements
If there are any additional requirements for your miner, install them by running:

```sh
python -m pip install -r ~/text_prompting/miners/vicuna/requirements.txt
```

## 3. Load and Run the Miner
Once you have installed the necessary packages, you can load and run the miner using PM2. Set the `CUDA_VISIBLE_DEVICES` variable to the GPU you want to use, and adjust the other variables according to your setup.

```sh
CUDA_VISIBLE_DEVICES=0 pm2 start ~/text_prompting/neurons/miners/vicuna/miner.py \
--name vicuna \
--interpreter <path-to-python-binary> -- \
--vicuna.model_name TheBloke/Wizard-Vicuna-7B-Uncensored-HF \
--wallet.name <wallet-name> \
--wallet.hotkey <wallet-hotkey> \
--netuid <netuid> \
--subtensor.network <network> \
--logging.debug \
--axon.port <port>
```

### Variable Explanation
- `--vicuna.model_name`: Specify any Vicuna style model.
- `--wallet.name`: Provide the name of your wallet.
- `--wallet.hotkey`: Enter your wallet's hotkey.
- `--netuid`: Use `8` for testnet.
- `--subtensor.network`: Specify the network you want to use (`finney`, `test`, `local`, etc).
- `--logging.debug`: Adjust the logging level according to your preference.
- `--axon.port`: Specify the port number you want to use.

## Conclusion
By following this guide, you should be able to setup and run a Vicuna miner using the text-prompting repository with PM2. Ensure that you monitor your processes and check the logs regularly for any issues or important information. For more details or if you encounter any problems, refer to the official documentation or seek help from the community.
