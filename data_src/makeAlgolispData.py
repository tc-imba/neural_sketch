#generate deepcoder data
import sys
import os
sys.path.append(os.path.abspath('./'))
sys.path.append(os.path.abspath('./ec'))

import pickle
import time
from collections import namedtuple
#Function = namedtuple('Function', ['src', 'sig', 'fun', 'bounds'])

from grammar import Grammar, NoCandidates
from utilities import flatten

from algolispPrimitives import tsymbol, algolispProductions, algolispPrimitives
from program import Application, Hole, Primitive, Index, Abstraction, ParseFailure
import math
import random
from type import Context, arrow, tint, tlist, UnificationFailure

from util.algolisp_util import convert_IO, tree_to_prog, make_holey_algolisp, AlgolispHole, tree_to_seq, seq_to_tree, tree_depth, check_subtree, tokenize_for_dc

from itertools import zip_longest, chain
from functools import reduce
import torch

from program_synthesis.algolisp.dataset import dataset
from program_synthesis.algolisp import arguments

from util.algolisp_pypy_util import test_program_on_IO

from program_synthesis.algolisp.dataset import executor
#I want a list of namedTuples

#Datum = namedtuple('Datum', ['tp', 'p', 'pseq', 'IO', 'sketch', 'sketchseq'])

basegrammar = Grammar.fromProductions(algolispProductions()) # Fix this

# with open('basegrammar.p', 'rb') as file:
# 	basegrammar = pickle.load(file)

#reweighted basegrammar:
# class FrontierEntry(object):
#     def __init__(
#             self,
#             program,
#             _=None,
#             logPrior=None,
#             logLikelihood=None,
#             logPosterior=None):
#         self.logPosterior = logPrior + logLikelihood if logPosterior is None else logPosterior
#         self.program = program
#         self.logPrior = logPrior
#         self.logLikelihood = logLikelihood

#     def __repr__(self):
#         return "FrontierEntry(program={self.program}, logPrior={self.logPrior}, logLikelihood={self.logLikelihood}".format(
#             self=self)


# class Frontier(object):
#     def __init__(self, frontier, task):
#         self.entries = frontier
#         self.task = task



def grouper(iterable, n, fillvalue=None):
	"Collect data into fixed-length chunks or blocks"
	# grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
	args = [iter(iterable)] * n
	return zip_longest(*args, fillvalue=fillvalue)

#redo this ...
class Datum():
	def __init__(self, tp, p, pseq, IO, sketch, sketchseq, reward, sketchprob, spec, schema_args):
		self.tp = tp
		self.p = p
		self.pseq = pseq
		self.IO = IO
		self.sketch = sketch
		self.sketchseq = sketchseq
		self.reward = reward
		self.sketchprob = sketchprob
		self.spec = spec
		self.schema_args = schema_args

	def __hash__(self): 
		return reduce(lambda a, b: hash(a + hash(b)), flatten(self.spec, abort=lambda x: type(x) is str), 0) + hash(self.p) + hash(self.sketch)

Batch = namedtuple('Batch', ['tps', 'ps', 'pseqs', 'IOs', 'sketchs', 'sketchseqs', 'rewards', 'sketchprobs','specs', 'schema_args'])

def convert_datum(ex,
				compute_sketches=False,
				top_k_sketches=20,
				inv_temp=1.0,
				reward_fn=None,
				sample_fn=None,
				dc_model=None,
				improved_dc_model=True,
				use_timeout=False,
				proper_type=False,
				only_passable=False,
				filter_depth=None,
				nHoles=4,
				exclude=None,
				include_only=None,
				#include_all=None,
				use_fixed_seed=False,
				limit_IO_size=None,
				use_IO=False,
				rng=None):
	if filter_depth:
		#filter_depth should be an iterable of depths that are allowed
		if not tree_depth(ex.code_tree) in filter_depth: return None

	if exclude:
		for subex in exclude:
			if any( check_subtree(ex.code_tree, subex) for subex in exclude): return None

	if include_only: 
		for subex in include_only:
			if not any( check_subtree(ex.code_tree, subex) for subex in include_only): return None

	#if include_all: assert False, "unimplemnted"


	#find IO
	IO = convert_IO(ex.tests) #TODO

	if limit_IO_size:
		tokenized = []
		for io in IO:
			if len(tokenize_for_dc(io, digit_enc=True)) > limit_IO_size:
				return None

	schema_args = ex.schema.args
	if only_passable:
		executor_ = executor.LispExecutor()
		hit_tree = test_program_on_IO(ex.code_tree, IO, schema_args, executor_)
		#hit_seq = test_program_on_IO(seq_to_tree(ex.code_sequence), IO, schema_args, executor_)
		#if not hit_tree==hit_seq: print("DATASET WARNING: tree and seq don't match, one fails tests and the other passes")
		if not hit_tree: return None
	# find tp
	if proper_type:
		assert False #arrow(some_stuff, tsymbol)
		out_tp = convert_tp(x.schema.return_type)
	else:
		tp = tsymbol
	# find program p
	pseq = tuple(ex.code_sequence)
	# find pseq
	if proper_type:
		assert False
	else:
		p = tree_to_prog(ex.code_tree)  # TODO: use correct grammar, and 
	spec = ex.text
	if compute_sketches:
		# find sketch
		#grammar = basegrammar if not dc_model else dc_model.infer_grammar(IO) #This line needs to change
		dc_input = spec if not use_IO else IO
		sketch, reward, sketchprob = make_holey_algolisp(p,
														top_k_sketches,
														tp,
														basegrammar=basegrammar,
														dcModel=dc_model,
														improved_dc_model=improved_dc_model,
														inv_temp=inv_temp,
														reward_fn=reward_fn,
														sample_fn=sample_fn,
														use_timeout=use_timeout,
														return_obj=AlgolispHole,
														dc_input=dc_input,
														nHoles=nHoles,
														use_fixed_seed=use_fixed_seed,
														rng=rng) #TODO
		# find sketchseq
		sketchseq = tuple(tree_to_seq(sketch.evaluate([])))
	else:
		sketch, sketchseq, reward, sketchprob = None, None, None, None
	return Datum(tp, p, pseq, IO, sketch, sketchseq, reward, sketchprob, spec, schema_args)

def batchloader(data_file,
				batchsize=100,
				compute_sketches=False,
				dc_model=None,
				improved_dc_model=True,
				shuffle=True,
				top_k_sketches=20,
				inv_temp=1.0,
				reward_fn=None,
				sample_fn=None,
				use_timeout=False,
				only_passable=False,
				filter_depth=None,
				nHoles=1,
				limit_data=False,
				use_fixed_seed=False,
				use_dataset_len=False,
				exclude=None,
				include_only=None,
				include_all=None,
				limit_IO_size=None,
				use_IO=False,
				seed=42):
	"""
	Note: exclude and include_only take lists of expressions!!! don't get confused
	"""

	mode = 'train' if data_file=='train' else 'eval'
	parser = arguments.get_arg_parser('Training AlgoLisp', mode)
	args = parser.parse_args([]) #this takes only the default values, allowing us to use the top-level parser for our code in main files
	args.cuda = not args.no_cuda and torch.cuda.is_available()

	args.batch_size = batchsize #doesn't even matter now

	if data_file == 'train':
		NearDataset, _ = dataset.get_dataset(args)
		dataset_len = 79214
	elif data_file == 'dev':
		_, NearDataset = dataset.get_dataset(args)
		assert not use_dataset_len
	elif data_file == 'eval':
		print("WARNING: right now 'eval' gives correct 'eval' test set")
		NearDataset = dataset.get_eval_dataset(args) # TODO:
		assert not use_dataset_len
	else:
		assert False

	seeded_random = random.Random(seed) #so that state is shared

	if use_dataset_len:
		inc_list = seeded_random.sample(range(dataset_len), use_dataset_len)
		counter = 0

	def remove_datum():
		if use_dataset_len:
			nonlocal counter
			rval = counter not in inc_list
			counter += 1
			return rval
		else:
			if limit_data:
				return not seeded_random.random() < limit_data
			else: 
				return False

	data = (convert_datum(ex,
			compute_sketches=compute_sketches,
			top_k_sketches=top_k_sketches,
			inv_temp=inv_temp,
			reward_fn=reward_fn,
			sample_fn=sample_fn,
			dc_model=dc_model,
			improved_dc_model=improved_dc_model,
			use_timeout=use_timeout,
			proper_type=False,
			only_passable=only_passable,
			filter_depth=filter_depth,
			nHoles=nHoles,
			exclude=exclude,
			include_only=include_only,
			use_fixed_seed=use_fixed_seed,
			limit_IO_size=limit_IO_size,
			use_IO=use_IO,
			rng=seeded_random if use_fixed_seed else None) for batch in NearDataset for ex in batch if not remove_datum() ) #I assume batch has one ex
	data = (x for x in data if x is not None)
	#figure out how to deal with these
	if batchsize==1:
		yield from data

	else:
		grouped_data = grouper(data, batchsize)
		for group in grouped_data:
			tps, ps, pseqs, IOs, sketchs, sketchseqs, rewards, sketchprobs, specs, schema_args = zip(*[
				(datum.tp, datum.p, datum.pseq, datum.IO, datum.sketch, datum.sketchseq, datum.reward, datum.sketchprob, datum.spec, datum.schema_args)
				for datum in group if datum is not None])
			yield Batch(tps, ps, pseqs, IOs, sketchs, sketchseqs, torch.FloatTensor(rewards) if any(r is not None for r in rewards) else None, torch.FloatTensor(sketchprobs) if any(s is not None for s in sketchprobs) else None, specs, schema_args)  # check that his work

		# for batch in NearDataset:
		# 	tps, ps, pseqs, IOs, sketchs, sketchseqs, rewards, sketchprobs, specs, schema_args = zip(*[
		# 		(datum.tp, datum.p, datum.pseq, datum.IO, datum.sketch, datum.sketchseq, datum.reward, datum.sketchprob, datum.spec, datum.schema_args)
		# 		for datum in (convert_datum(ex,
		# 							compute_sketches=compute_sketches,
		# 							top_k_sketches=top_k_sketches,
		# 							inv_temp=inv_temp,
		# 							reward_fn=reward_fn,
		# 							sample_fn=sample_fn,
		# 							dc_model=dc_model,
		# 							improved_dc_model=improved_dc_model,
		# 							use_timeout=use_timeout,
		# 							proper_type=False,
		# 							only_passable=only_passable,
		# 							filter_depth=filter_depth) for ex in batch)
		# 		 					if datum is not None])
			
		# 	yield Batch(tps, ps, pseqs, IOs, sketchs, sketchseqs, torch.FloatTensor(rewards) if any(r is not None for r in rewards) else None, torch.FloatTensor(sketchprobs) if any(s is not None for s in sketchprobs) else None, specs, schema_args)  # check that his work

from frontier import Frontier, FrontierEntry
from task import Task

def reweightbasegrammar(basegrammar, pseudoCounts, filter_depth=None, size=None):
	frontiers = [] 
	for datum in islice(batchloader('train',
								batchsize=1,
								compute_sketches=False,
								filter_depth=filter_depth), size): #TODO
		#class Task(object):
		#def __init__(self, name, request, examples, features=None, cache=False):
		frontiers.append( Frontier([FrontierEntry(datum.p, logPrior=basegrammar.logLikelihood(datum.tp, datum.p), logLikelihood=0)], Task('dummyName', datum.tp, []) ) )
	
	return basegrammar.insideOutside(frontiers, pseudoCounts, iterations=1)




if __name__=='__main__':
	from itertools import islice
	# algolispProductions()
	# d = islice(batchloader('train', batchsize=200, compute_sketches=True, dc_model=None, improved_dc_model=True, shuffle=True, top_k_sketches=20, inv_temp=1.0, reward_fn=None, sample_fn=None, use_timeout=False),100)
	# for datum in d:
	# 	print("program:", datum.p)
	# 	print("sketch: ", datum.sketch)
	# 	print(len(datum.pseq))
	# 	print()
	from collections import Counter
	c = Counter()
	max_len = 0
	for i, d in enumerate(batchloader('eval',
				batchsize=1,
				compute_sketches=False,
				only_passable=False)):
		c.update([len(d.pseq)])
		max_len = max(len(d.pseq) , max_len )


	print("max_len:", max_len)
	print(c)

	# assert False
	print(basegrammar)
	g = reweightbasegrammar(basegrammar, 0.1, filter_depth=None, size=None)
	print(g)

	print('saving')

	with open('basegrammar.p','wb') as savefile:
		pickle.dump(g, savefile)

	for i in c:
		print(i, c[i])
