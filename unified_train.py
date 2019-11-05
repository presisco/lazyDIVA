from __future__ import absolute_import, division, print_function

import random
import time

import numpy as np
import episodes as eps
# Import TensorFlow >= 1.9 and enable eager execution
import tensorflow as tf

import loss
from graph.graph import Graph
from pathfinder.brute.bfsfinder import BFSFinder
from pathfinder.lstmfinder import LSTMFinder
from pathreasoner.cnn_reasoner import CNNReasoner

epoch = 25
emb_size = 100
rollouts = 5
max_path_length = 5

task = 'concept:athletehomestadium'
graph = Graph('graph.db')
graph.prohibit_relation(task)
checkpoint_dir = 'checkpoints/'

train_set = []
test_set = []

teacher = BFSFinder(env_graph=graph, max_path_length=max_path_length)
posterior = LSTMFinder(graph=graph, emb_size=emb_size, max_path_length=max_path_length, prior=False)
prior = LSTMFinder(graph=graph, emb_size=emb_size, max_path_length=max_path_length, prior=True)
path_reasoner = CNNReasoner(graph=graph, input_width=emb_size * 2, max_path_length=max_path_length)

likelihood_optimizer = tf.optimizers.Adam(1e-4)
# 使用SGD避免训练失败
posterior_optimizer = tf.optimizers.SGD(1e-2)
# 使用Adam提升学习速度
prior_optimizer = tf.optimizers.Adam(1e-3)

posterior_checkpoint = tf.train.Checkpoint(model=posterior)
posterior_chkpt_file = 'checkpoints/posterior_fine'

prior_checkpoint = tf.train.Checkpoint(optimizer=prior_optimizer, model=prior)
prior_chkpt_file = 'checkpoints/prior'

likelihood_checkpoint = tf.train.Checkpoint(optimizer=likelihood_optimizer, model=path_reasoner)
likelihood_chkpt_file = 'checkpoints/likelihood'


# 搜索失败时重新训练
def teach_posterior(from_id, to_id):
    print('reteaching posterior')
    episode = eps.find_episode(from_id, to_id)

    if episode['type'] == '+':
        rel_emb = positive_rel_emb
    else:
        rel_emb = negative_rel_emb

    paths = episode['paths']
    if paths is None:
        states = teacher.paths_between(sample['from_id'], sample['to_id'], 5)
        paths = list(map(lambda s: s.path, states))

    for path in paths:
        probs, gradients = posterior.learn_from_teacher(
            path=path,
            reward=1.0,
            rel_emb=rel_emb
        )
        for gradient in gradients:
            posterior_optimizer.apply_gradients(zip(gradient, posterior.trainable_variables))


# 训练posterior
def train_posterior(positive, negative, rel_emb):
    all_probs = []
    for reward, path in positive + negative:
        probs, gradients = posterior.learn_from_teacher(
            path=path,
            reward=reward,
            rel_emb=rel_emb
        )
        all_probs = all_probs + probs

        for gradient in gradients:
            posterior_optimizer.apply_gradients(zip(gradient, posterior.trainable_variables))

    return all_probs


# 训练likelihood
def train_likelihood(paths, label):
    for path in paths:
        # 分类损失为0.0-1.0
        classify_loss, gradient = path_reasoner.learn_from_label(path, label)
        likelihood_optimizer.apply_gradients(zip(gradient, path_reasoner.trainable_variables))


# 训练prior
def train_prior(results):
    all_probs = []
    for reward, path in results:
        probs, gradients = prior.learn_from_teacher(
            path=path,
            reward=reward
        )
        all_probs = all_probs + probs

        for gradient in gradients:
            prior_optimizer.apply_gradients(zip(gradient, prior.trainable_variables))

    return all_probs


def rollout_episode(episode, rel_emb, label):
    positive_results = []
    negative_results = []

    # 查找n条路径
    path_states = posterior.paths_between(episode['from_id'], episode['to_id'], rollouts, rel_emb)

    # 获得路径的奖励值
    for state in path_states:
        if state.path[-1] != episode['to_id']:
            negative_results.append((search_failure_reward, state.path))
            continue

        # 需要反转分类损失作为路径搜索奖励
        classify_loss, gradient = path_reasoner.learn_from_label(state.path, label)
        positive_results.append((1.0 - classify_loss, state.path))

    return positive_results, negative_results


train_samples = eps.all_episodes()
random.shuffle(train_samples)
train_samples = train_samples[:100]
print('using {} train samples'.format(len(train_samples)))

test_samples = graph.test_samples_of(task)
# train_samples = [{
#     'from_id': 37036,
#     'to_id': 68461,
#     'type': '-'
# }]
positive_rel_emb = graph.vec_of_rel_name(task)
negative_rel_emb = np.zeros(emb_size, dtype='f4')
search_failure_reward = -0.05

posterior_checkpoint.restore('checkpoints/posterior-25')

for i in range(epoch):
    epoch_start = time.time()
    all_loss = np.zeros(0)
    stage = i % 3

    for index, sample in enumerate(train_samples):
        label = loss.type_to_label(sample['type'])
        if sample['type'] == '+':
            rel_emb = positive_rel_emb
        else:
            rel_emb = negative_rel_emb

        positive, negative = rollout_episode(sample, rel_emb, label)
        all_loss = np.concatenate((all_loss, list(map(lambda r: 1.0 - r[0], positive))))

        # 训练posterior
        if stage == 0:
            train_posterior(positive, negative, rel_emb)
            # 成功路径过少，需要重新监督学习
            if len(positive) < 2:
                teach_posterior(sample['from_id'], sample['to_id'])
        # 训练likelihood
        elif stage == 1:
            paths = list(map(lambda r: r[1], positive))
            train_likelihood(paths, label)
        # 训练prior
        else:
            train_prior(positive)

    avg_loss = np.average(all_loss)
    min_loss = np.min(all_loss)
    print('epoch: {} takes {:.2f}s, min: {:.2f}, avg: {:.2f}, max: {:.2f}'.format(
        i + 1,
        time.time() - epoch_start,
        np.min(all_loss),
        np.average(all_loss),
        np.max(all_loss)
    ))

    if stage == 0:
        posterior_checkpoint.save(posterior_chkpt_file)
    elif stage == 1:
        likelihood_checkpoint.save(likelihood_chkpt_file)
    else:
        prior_checkpoint.save(prior_chkpt_file)

print('finished!')
