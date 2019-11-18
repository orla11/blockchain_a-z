# Create a Cryptocurrency

# Importing libraries
import datetime
import hashlib
import json
from flask import Flask, jsonify, request
import requests
from uuid import uuid4
import pickle, bz2
from urllib.parse import urlparse

# 1 - Create Blockchain
class Blockchain:

    def __init__(self):
        # Blockchain initialization
        self.chain = []
        self.transactions = []
        self.nodes = set() # nodes of the network 

        _, genesis_block = self.proof_of_work()
        self.add_block(genesis_block, skip_return=True)

        self.backup_chain()

    def add_block(self, block, skip_return=False):
        self.chain.append(block)
        self.backup_chain()

        if skip_return is False:
            return block

    def prepare_block(self, proof, previous_hash):
        block = {'index': len(self.chain) + 1,
                 'timestamp': str(datetime.datetime.now()),
                 'proof': proof,
                 'previous_hash': previous_hash,
                 'transactions': self.transactions}

        self.transactions = [] # emptying transactions list
        
        return block

    def backup_chain(self):
        sfile = bz2.BZ2File('chain_bk_1','w')
        pickle.dump(self.chain, sfile)

    def load_chain(self):
        sfile = bz2.BZ2File('chain_bk_1','rb')
        return pickle.load(sfile)

    def set_proof(self, block, test_proof):
        block['proof'] = test_proof
        return block
    
    def get_previous_block(self):
        # Return last block in the chain
        return self.chain[-1]

    def proof_of_work(self):
        new_proof = 1
        check_proof = False

        if len(self.chain) is 0: # genesis block
            previous_hash = '0'
            new_block = self.prepare_block(proof = 1, previous_hash = previous_hash)
        else: # usual block
            previous_hash = self.hash(self.chain[-1])
            new_block = self.prepare_block(new_proof,previous_hash)

        while check_proof is False:
            # !!! we could set the new timestamp here before starting hashing again
            hash_operation = self.hash(new_block)
            if hash_operation[:4] == '0000':
                check_proof = True
            else:
                new_proof += 1
                new_block = self.set_proof(new_block,new_proof)
        
        return new_proof, new_block

    def hash(self, block):
        encoded_block = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest()

    def get_chain(self):
        new_chain = self.load_chain()
        for index,block in enumerate(new_chain):
            hash_block = self.hash(block)
            new_chain[index].update({'hash': hash_block})     

        return new_chain

    def is_chain_valid(self, chain):
        previous_block = chain[0]
        block_index    = 1

        while block_index < len(chain):
            block = chain[block_index]

            if block['previous_hash'] != self.hash(previous_block):
                return False
            
            hash_operation = self.hash(block)

            if hash_operation[:4] != '0000':
                return False

            previous_block = block
            block_index += 1
    
        return True

    def add_transaction(self, sender, receiver, amount):
        self.transactions.append({
            'sender': sender,
            'receiver': receiver,
            'amount': amount
        })

        prev_block = self.get_previous_block()

        return prev_block['index'] + 1

    def add_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def replace_chain(self):
        network = self.nodes
        longest_chain = None
        max_length = len(self.chain)

        for node in network:
            response = requests.get(f'http://{node}/get_chain')

            if response.status_code == 200:
                length = response.json()['depth']
                chain = response.json()['chain']

                if length > max_length:
                    max_length = length
                    longest_chain = chain

        if longest_chain:
            self.chain = longest_chain
            self.backup_chain()
            return True
        else:
            return False
                
# 2 - Mining the Blockchain

# Initialize WebApp
app = Flask(__name__)

# Creating an address for the node on Port 5001
node_address = str(uuid4()).replace('-', '')

# Creating Blockchain
blockchain = Blockchain()

# Mining new block
@app.route('/mine_block', methods=['GET'])
def mine_block():
    # Block fee/reward
    blockchain.add_transaction(sender = node_address,
                               receiver = 'Bill',
                               amount = 1)

    proof, new_block = blockchain.proof_of_work()

    mined_block = blockchain.add_block(new_block)

    response = {'message': 'Congratulations, you just mined a block!',
                'index': mined_block['index'],
                'timestamp': mined_block['timestamp'],
                'proof': mined_block['proof'],
                'transactions': mined_block['transactions'],
                'previous_hash': mined_block['previous_hash'],
                'hash': blockchain.hash(mined_block)}
    
    return jsonify(response), 200

# Add a transaction
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    json = request.get_json()

    transaction_keys = ['sender','recevier','amount']

    if not all (key in json for key in transaction_keys):
        return 'Some elements of the transaction are missing', 400

    index = blockchain.add_transaction(json['sender'],json['receiver'],json['amount'])
    response = {'messagge': f'This transaction will be added to Block {index}'}

    return jsonify(response), 201

# Getting the full Blockchain
@app.route('/get_chain', methods=['GET'])
def get_chain():
    response = {'chain': blockchain.get_chain(),
                'depth': len(blockchain.chain)}

    return jsonify(response), 200

# Check if the Blockchain is valid
@app.route('/is_valid', methods=['GET'])
def is_valid():
    is_valid = blockchain.is_chain_valid(blockchain.chain)
    
    if is_valid:
        response = {'message': 'The Blockchain is valid.'}
    else:
        response = {'message': 'The Blockchain is not valid.'}

    return jsonify(response), 200

# 3 - Decentralizing the Blockchain

# Connecting new nodes
@app.route('/connect_node', methods=['POST'])
def connect_node():
    json = request.get_json()
    nodes = json.get('nodes')
    if nodes is None:
        return "No nodes", 400
    for node in nodes:
        blockchain.add_node(node)
    response = {'message': 'All the nodes are now connected. The Fastcoin blockchain now contains the following nodes',
                'total_nodes': list(blockchain.nodes)}

    return jsonify(response), 201

# Replacing the chain by the longest chain if needed
@app.route('/replace_chain', methods=['GET'])
def replace_chain():
    is_chain_replaced = blockchain.replace_chain()
    
    if is_chain_replaced:
        response = {'message': 'The node has different chains. The chain was replaced by the longest one.',
                    'chain': blockchain.chain}
    else:
        response = {'message': 'The chain is the longest.',
                    'actual_chain': blockchain.chain}

    return jsonify(response), 200
    
# Running the App
app.run(host='0.0.0.0',port=5001)