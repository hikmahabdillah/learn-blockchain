import sys
import hashlib # Import hashlib for hashing
import json

from time import time #for time stamp
from uuid import uuid4 #for unique id

from flask import Flask
from flask.globals import request
from flask.json import jsonify #for json response

import requests #for http requests
from urllib.parse import urlparse #for parsing urls

class Blockchain(object):
  # Initialize the blockchain

  # customable difficulty target
  difficulty_target = "0000" # Difficulty target for proof of work

  #hashing block function 
  def hash_block(self, block):
    block_encoded = json.dumps(block, sort_keys=True).encode() # sorting keys for consistent hashing
    return hashlib.sha256(block_encoded).hexdigest()
  
  # constructor method
  def __init__(self): #generate genesis block
    # Initialize to add each node
    self.nodes = set() #

    self.chain = [] #save all blocks in chain
    
    self.current_transactions = [] #save all transactions in current block

    genesis_hash = self.hash_block("genesis_block") #hash genesis block
    
    self.add_block(
      hash_of_previous_block=genesis_hash,
      nonce = self.proof_of_work(0, genesis_hash, []) # Get a valid nonce for the genesis block, # proof of work
    )
  
  # Method to register a new node
  def add_node(self, address):
    parsed_url = urlparse(address)
    self.nodes.add(parsed_url.netloc) # Add the node to the set of nodes
    print(parsed_url.netloc, "added to nodes") # Print the node that was added

  def valid_chain(self, chain):
    last_block = chain[0]
    current_index = 1

    while current_index < len(chain):
      block = chain[current_index]

      # Check if the hash of the previous block is correct
      #previous_hash from current block != hash of last block
      #previous_hash from block 1 != hash of block 0
      if block['hash_of_previous_block'] != self.hash_block(last_block):
        return False
      
      if not self.valid_proof(
        current_index,
        block['hash_of_previous_block'],
        block['transaction'],
        block['nonce']):
        return False
      
      last_block = block # Update the last block
      current_index += 1 # Move to the next block
    
    return True # If all checks passed, the chain is valid
  
  # update the chain with a new chain, synchronize with other nodes
  def update_chain(self):
    #search neighboring nodes for a longer chain
    neighbours = self.nodes # Get the set of nodes
    new_chain = None # Initialize new_chain to None

    # Loop through each node to find the longest chain
    max_length = len(self.chain) # Get the length of the current chain

    for node in neighbours:
      response = requests.get(f'http://{node}/blockchain')

      if response.status_code == 200: # If the request was successful
        length = response.json()['length']
        chain = response.json()['chain']

        # Check if the length of the chain is greater than the current max_length and if the chain is valid
        if length > max_length and self.valid_chain(chain):
          max_length = length # Update max_length if the new chain is longer
          new_chain = chain # Update new_chain if a longer valid chain is found
        
          if new_chain: # If a new chain was found
            self.chain = new_chain # Update the current chain to the new chain
            return True # Return True indicating the chain was updated
            
    return False # Return False if no valid longer chain was found
  

  # method to get valid nonce
  def proof_of_work(self, index, hash_of_previous_block, transactions):
    nonce = 0 # Start with nonce 0
    
    # Loop until a valid nonce is found
    while self.valid_proof(index, hash_of_previous_block, transactions, nonce) is False:
      nonce += 1
    return nonce

   # Function to validate proof (whether nonce generates hash according to difficulty)
  def valid_proof(self, index, hash_of_previous_block, transactions, nonce):
    content = f"{index}{hash_of_previous_block}{transactions}{nonce}".encode() # encode the content
    content_hash = hashlib.sha256(content).hexdigest() # hash the content
    
    # Check if the hash starts with the difficulty target(0000)
    # return content_hash.startswith(self.difficulty_target)

    #cut off the hash to the length of the difficulty target
    return content_hash[:len(self.difficulty_target)] == self.difficulty_target

  # Function to add a new block to the chain
  def add_block(self, nonce,hash_of_previous_block):
    block = {
      'index': len(self.chain), # index of the block
      'timestamp': time(), # timestamp of the block
      'transaction': self.current_transactions, # transactions in the block
      'nonce': nonce, # nonce for proof of work
      'hash_of_previous_block': hash_of_previous_block # hash of the previous block
    }

    # reset when block is added, cause we are starting with a new block and new transactions
    self.current_transactions = [] # reset current transactions

    self.chain.append(block) # add block to the chain
    return block
  
  # Function to add a new transaction to the current block
  def add_transaction(self, sender, recipient, amount):
    self.current_transactions.append({
      'amount': amount,
      'recipient': recipient,
      'sender': sender
    })

    # The index of the block that will hold this transaction is the last block's index + 1
    return self.last_block['index'] + 1 # return the index of the block that will hold this transaction
  
  @property
  def last_block(self):
    return self.chain[-1] 

app = Flask(__name__)

node_identifier = str(uuid4()).replace('-', '') # Generate a unique node identifier

blockchain = Blockchain() # Create a new instance of the Blockchain
# This is the main entry point for the Flask application
#routes
@app.route('/blockchain', methods=['GET'])
def get_full_chain():
    response = {
        'chain': blockchain.chain, # Get the full blockchain
        'length': len(blockchain.chain), # Length of the blockchain
    }
    return jsonify(response), 200

#route for mining a new block
@app.route('/mine', methods=['GET'])
def mine_block():
  blockchain.add_transaction(
    sender="0", # sender is 0 for mining rewards
    recipient=node_identifier, # recipient is the node that mined the block
    amount=1, # mining reward is 1 unit
  )

  last_block_hash = blockchain.hash_block(blockchain.last_block) # Hash the last block

  index = len(blockchain.chain) # Index of the new block
  nonce = blockchain.proof_of_work(index, last_block_hash, blockchain.current_transactions)

  block = blockchain.add_block(nonce, last_block_hash) # Add the new block to the chain
  response = {
    'message': 'New Block Forged',
    'index': block['index'],
    'hash_of_previous_block': block['hash_of_previous_block'],
    'nonce': block['nonce'],
    'transaction': block['transaction'],
  }

  return jsonify(response), 200

#route for adding a new transaction
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
  values = request.get_json() # Get the JSON data from the request
  # Check if the required fields are in the JSON data
  required_fields = ['sender', 'recipient', 'amount']
  if not all(field in values for field in required_fields):
    return 'Missing values', 400
  
  # Add the transaction to the blockchain
  index = blockchain.add_transaction(
    values['sender'],
    values['recipient'],
    values['amount']
  )

  response = {
    'message': f'Transaction will be added to Block {index}',
  }

  return jsonify(response), 201

#route for registering a new node
@app.route('/nodes/add_nodes', methods=['POST'])
def add_nodes():
  values = request.get_json() # Get the JSON data from the request
  nodes = values.get('nodes') # Get the list of nodes from the JSON data

  if nodes is None:
    return 'Error: Please supply a valid list of nodes', 400
  
  for node in nodes:
    blockchain.add_node(node)

  response = {
    'message': 'New nodes have been added',
    'nodes': list(blockchain.nodes) # Return the list of nodes
  }

  return jsonify(response), 201

# update chain
@app.route('/nodes/sync', methods=['GET'])
def sync_chain():
  updated = blockchain.update_chain()
  if updated:
    response = {
      'message': 'Chain updated successfully with a new data',
      'blockchain': blockchain.chain
    }
  else:
    response = {
      'message': 'No new data found, chain is up to date',
      'blockchain': blockchain.chain
    } 

  # Return the response as JSON
  return jsonify(response), 200

if __name__ == '__main__':
  # Run the Flask app
  app.run(host='0.0.0.0', port=int(sys.argv[1])) # Run on all interfaces on port int(sys.r)

