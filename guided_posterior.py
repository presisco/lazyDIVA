from __future__ import absolute_import, division, print_function

import sys
import time

import numpy as np
# Import TensorFlow >= 1.9 and enable eager execution
import tensorflow as tf

import episodes
from graph.graph import Graph
from pathfinder.lstmfinder import LSTMFinder
from train_tools import teach_finder, show_type_distribution

teacher_epoch = 25
teacher_path_count = 5
max_path_length = 5
database = 'weibo'
task = 'event_type'
emb_size = 100
sample_count = 500
save_checkpoint = True

graph = Graph(database + '.db')
graph.prohibit_relation('entertainment')
graph.prohibit_relation('political')
rel_embs = {
    10: graph.vec_of_rel_name('entertainment'),
    12: graph.vec_of_rel_name('political')
}

student = LSTMFinder(graph=graph, emb_size=emb_size, graph_sage_state=False, max_path_length=max_path_length)
optimizer = tf.optimizers.Adam(1e-3)
checkpoint = tf.train.Checkpoint(optimizer=optimizer, model=student)

chkpt_file = 'checkpoints/{}/{}/guided/posterior'.format(database, task.replace('/', '_').replace(':', '_'))

print('eager mode: {}'.format(tf.executing_eagerly()))

samples = episodes.load_previous_episodes('{}.json'.format(task.replace(':', '_').replace('/', '_')))
# random.shuffle(samples)
samples = samples[:sample_count]

show_type_distribution(samples)


def learn_epoch(epoch, supervised_samples):
    start_time = time.time()
    probs = []
    for index, sample in enumerate(supervised_samples):
        probs = probs + teach_finder(
            finder=student,
            optimizer=optimizer,
            sample=sample,
            rel_emb=rel_embs[sample['rid']]
        )

    np_probs = np.array(probs)
    print('epoch: {} finished in {:.2f} seconds, prob stats: avg: {:.4f}'.format(
        epoch + 1,
        time.time() - start_time,
        np.average(np_probs)
    ))


print('guided learning started! using {} samples'.format(len(samples)))
for i in range(teacher_epoch):
    learn_epoch(i, samples)

if save_checkpoint:
    checkpoint.save(chkpt_file)
print('pre-train finished!')
