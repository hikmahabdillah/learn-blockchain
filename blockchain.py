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
    block_encoded = json.dumps(block, sort_keys=True) # sorting keys for consistent hashing
    return hashlib.sha256(block_encoded.encode()).hexdigest()
  
  # constructor method
  def __init__(self): #generate genesis block
    # Initialize to add each node
    self.nodes = set() 

    self.chain = [] #save all blocks in chainj
    
    self.current_transactions = [] #save all transactions in current block
    genesis_hash = self.hash_block("genesis_block") #hash genesis block
    nonce = self.proof_of_work(0, genesis_hash, []) # Get a valid nonce for the genesis block
    
    self.add_block(
      hash_of_previous_block=genesis_hash,
      nonce = nonce, # proof of work
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
      if block['hash_of_previous_block'] != self.hash_block(last_block):
        return False
      
      if not self.valid_proof(
        current_index,
        block['hash_of_previous_block'],
        block['transactions'],
        block['nonce']
      ):
        return False
      
      last_block = block # Update the last block
      current_index += 1 # Move to the next block
    
    return True # If all checks passed, the chain is valid


  # method to get valid nonce
  def proof_of_work(self, index, hash_of_previous_block, transactions, nonce=0):
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
  def add_block(self, hash_of_previous_block, nonce):
    block = {
      'index': len(self.chain) + 1, # index of the block
      'timestamp': time(), # timestamp of the block
      'transactions': self.current_transactions, # transactions in the block
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
      'sender': sender,
      'recipient': recipient
    })

    # The index of the block that will hold this transaction is the last block's index + 1
    return self.last_block['index'] + 1 # return the index of the block that will hold this transaction
  
  @property
  def last_block(self):
    return self.chain[-1] if self.chain else None

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

  last_block = blockchain.last_block # Get the last block
  hash_of_previous_block = blockchain.hash_block(last_block) # Hash the last block

  index = len(blockchain.chain) # Index of the new block
  nonce = blockchain.proof_of_work(index, hash_of_previous_block, blockchain.current_transactions)

  block = blockchain.add_block(hash_of_previous_block=hash_of_previous_block, nonce=nonce) # Add the new block to the chain
  response = {
    'message': 'New Block Forged',
    'index': block['index'],
    'hash_of_previous_block': block['hash_of_previous_block'],
    'nonce': block['nonce'],
    'transactions': block['transactions'],
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

if __name__ == '__main__':
  # Run the Flask app
  app.run(host='0.0.0.0', port=int(sys.argv[1])) # Run on all interfaces on port int(sys.r)

