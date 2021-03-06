import argparse
import socket
import random
import capnp

import brain_capnp
import time

import numpy as np

from keras.models import Sequential
from keras.layers import Dense, LSTM, Dropout, Convolution1D, MaxPooling1D, GlobalMaxPooling1D, Embedding, Flatten
from keras.optimizers import SGD, Nadam, Adam, Adadelta
import math
import os
import scipy.stats
from scipy.stats.stats import pearsonr
import re
import random

from threading import Lock
mutex = Lock()
import pickle
import gc

total_packet_count = 0
NN_packet_count = 0
oracle_packet_count = 0
random_packet_count = 0

def calculateSortedness():
    global NN_packet_count
    global total_packet_count
    global oracle_packet_count
    global random_packet_count
    x =  os.popen("sudo ovs-ofctl dump-flows ovsbr0 -OOpenFlow14 | grep -v 'CONTROLLER' | awk '{print $4,$9}'").read()
    res = re.findall('\=([0-9]{1,6}).*\=([0-9]{1,6})', x)
    res = [(int(x),int(y)) for x,y in res]
    random.shuffle(res)
    A = res[:]
    B = res[:]
    B.sort(key=lambda x: x[1])
    A.sort(key=lambda x: x[0])
    C = res[len(res)/2:]
    D = B[len(res)/2:]
    E = A[len(res)/2:]
    # Calculate speedup
    old = sum([x for x,y in C])
    new = sum([x for x,y in D])
    oracle = sum([x for x,y in E])
    everything = sum([x for x,y in res])
    tau, p_value = scipy.stats.kendalltau(A,res)

    NN_packet_count += new
    oracle_packet_count += oracle
    total_packet_count += everything
    random_packet_count += old
    with open("total.txt", "a") as myfile:
        myfile.write("{0},{1},{2},{3}\n".format(NN_packet_count, oracle_packet_count, total_packet_count, random_packet_count))

    corr_x = [x for x,y in D]
    corr_y = [x for x,y in E]
    correlation, p_value = pearsonr(scipy.array(corr_x), scipy.array(corr_y))
    return tau, float(new) / old, float(oracle) / old, float(new)/everything, float(oracle)/everything, correlation, p_value
import sys

class PriorityImpl(brain_capnp.Brain.Priority.Server):
        def __init__(self, value):
            self.value = value

        def read(self, **kwargs):
            return self.value

def ConvertToOneHot(A):
    result = []
    for x in A:
        temp = [0]*5
        if x > 0.1:
            temp[4] = 1
        elif x > 0.01:
            temp[3] = 1
        elif x > 0.005:
            temp[2] = 1
        elif x > 0.001:
            temp[1] = 1
        else:
            temp[0] = 1
        result.append(temp)
    return result

from itertools import islice

class Dataset(object):
    def __init__(self, example, expected, count):
        big_end = len(expected)*75/100
        
        self.training_expected = expected[:big_end]
        self.training_example = example[:big_end]
        self.test_expected = expected[big_end:]
        self.test_example = example[big_end:]
        self.test_counts = count[big_end:]

def getModel():
    #self.model.add(Dropout(0.2))
    
    model = Sequential()

    model.add(Dense(50, input_dim=16, activation='relu', init='uniform'))
    model.add(Dropout(0.20))
    model.add(Dense(50, activation='relu', init='uniform'))
    model.add(Dropout(0.20))
    model.add(Dense(50, activation='relu', init='uniform'))
    model.add(Dropout(0.20))
    model.add(Dense(50, activation='relu', init='uniform'))
    model.add(Dropout(0.20))
    
    model.add(Dense(5, init='uniform', activation='sigmoid'))

    sgd = Adadelta()
    model.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])
    return model


class BrainImpl(brain_capnp.Brain.Server):
    def __init__(self):
        self.size = 1
        self.max = 1000.

        # binary_crossentropy
        #self.model.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])
        self.example = []
        self.expected = []
        self.exact_counts = []
        self.count = []
        self.global_example = []
        self.global_expected = []

	self.model = getModel()

        self.generation = 0
        self.count = 0
        self.model.summary()
        self.counter = 0
        self.save_counter = 0
        expire_buffer = []
        
    def predict(self, packet, _context, **kwargs):
        mutex.acquire()
        sample = [int(x.value) for x in packet.data]
        sample = np.array(sample)

        input = np.array([sample])
        
        result = self.model.predict(input)
        r = result[0]
        i = np.argmax(r)+1
        mutex.release()
        return PriorityImpl(int(i))

    def store_results(self, counts, examples):
        #print examples

        testdata = []
        for x in examples:
            temp = np.array([x])
            temp = self.model.predict(temp)[0]
            temp = np.argmax(temp)
            temp += 1
            
            testdata.append(temp)
            
        #testdata = [(np.argmax(self.model.predict(np.array(x)))+1) for x in examples]
        result = zip(counts, examples, testdata)
        #print result
        total = sum([x for x,y,z in result])
        
        random.shuffle(result)
        result.sort(key=lambda x: x[0])
        oracle = sum([x for x,y,z in result[len(result)/2:]])
        
        random.shuffle(result)
        rand = sum([x for x,y,z in result[len(result)/2:]])
        result.sort(key=lambda x: x[2])
        nn = sum([x for x,y,z in result[len(result)/2:]])

        with open("output.txt", "a") as myfile:
            myfile.write("{0},{1},{2},{3}\n".format(self.generation, float(oracle)/total, float(nn)/total, float(nn)/float(rand)))
            self.generation += 1
        
    def learn(self, packet, priority, _context, **kwargs):
        mutex.acquire()
        print "learn:"
        print priority.value
        #l = [0]
        p = int(priority.value) / 2000.
        if p > 1:
            p = 1.0
        print p
        sample = [int(x.value) for x in packet.data]
        sample = np.array(sample)
        self.example.append(sample)
        self.expected.append(p)
        self.exact_counts.append(int(priority.value))

        print p
        
        if len(self.example) >= 100:
            self.expected = ConvertToOneHot(self.expected)
            self.store_results(self.exact_counts, self.example)
            self.model.fit(np.array(self.example), np.array(self.expected), batch_size=100, nb_epoch=5)
            #scores = self.model.evaluate(np.array(self.example), np.array(self.expected))
            #print("%s: %.2f%%" % (self.model.metrics_names[1], scores[1]*100))
        
            #tau, speedup, oracle, new_of_everything, oracle_of_everything, correlation, p_value = calculateSortedness()
            #while math.isnan(tau) or tau <= 0:
            #    tau = calculateSortedness()
        
            pickle.dump((self.expected, self.example, self.exact_counts), open("/data2/packets/save-{0}.p".format(self.save_counter), "wb"))
            self.expected = []
            self.example = []
            self.exact_counts = []
    
        #self.save_counter += 1
        mutex.release()
            
        
        
def main():
        address = "127.0.0.1:3333"
        brain = BrainImpl()
        server = capnp.TwoPartyServer(address, bootstrap=brain)
        server.run_forever()

if __name__ =='__main__':
        main()
