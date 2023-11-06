# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 Opentensor Foundation

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import re
import torch
import math
from fuzzywuzzy import fuzz
from typing import List
from .config import RewardModelType
from .reward import BaseRewardModel
from collections import Counter, deque
from transformers import BertTokenizer

# TODO: Use CLI arguments to set blacklist values: the most important being the boundary value and max_size
class Blacklist(BaseRewardModel):

    @property
    def name(self) -> str:
        return RewardModelType.blacklist.value

    def __init__(self, 
        boundary:float = 3, 
        partia_ratio_boundary:float = 90, 
        max_size:int = 1_000_000, 
        n_min:int = 5, 
        n_max:int = 14, 
        word_limit:int = 2000, 
        A:float = 1.3, 
        preprocess:str = '[^(\\w|\\s)]'
    ):
        """N-gram blacklist reward model which penalizes overused phrases in the network

        Args:
            boundary (float, optional): Cutoff for flagging completions and giving zero reward. Defaults to 3.
            partial_ratio_boundary (float, optional): Cutoff for flagging completions in matching completion with counter and giving zero reward. Defaults to 90.
            max_size (int, optional): Maximum size of sliding window to use for aggregating ngrams. Defaults to 1_000_000.
            n_min (int, optional): Smallest ngram size. Defaults to 5.
            n_max (int, optional): Largest ngram size. Defaults to 14.
            word_limit (int, optional): Maximum word length, to prevent extremely long completions from overworking the queue. Defaults to 2000.
            A (float, optional): Exponent used in significance scoring, smaller A gives more weight to smaller ngrams. Values of 1.1-2 are recommended. Defaults to 1.1.
            preprocess (str, optional): Regex preprocessing string to make text more uniform. Defaults to '[^(\w|\s)]'.
        """
        super().__init__()

        self.deque = deque(maxlen=max_size)
        self.counter = {}

        self.n_min = n_min
        self.n_max = n_max
        self.word_limit = word_limit

        self.significance_scores = {}  # Store significance scores
        self.A = A
        self.boundary = boundary
        self.partial_ratio_boundary = partial_ratio_boundary

        self.preprocess = re.compile(preprocess) if preprocess else None
        self._last_update = 0

        self.support = 0.01 
        self.error = 0.000005 # Should be as small as possible, but decreasing it further will increase memory usage. 
        self.window = math.ceil(1/self.error) # Window size, counter would get pruned once for each window. 
        self.b_current = 1 # Bucket index.
        self.num_ngram = 0
        self.num_completion = 0
        self.tokenizer = BertTokenizer.from_pretrained("bert-base-cased")
        
        # windowling 
        # what if every 6 hours, num_ngram / num_completion / num_counter / b_current * 0.5, 


    def add(self, texts: List[str]):
        """Extract and add n-grams from a list of texts to counter

        Args:
            texts (list): batch of completion texts
        """

        for text in texts:
            # Extract n-grams from lowercased text
            ngrams = self.extract_ngrams(text.lower())

            if ngrams:
                self._add_ngrams(ngrams)


    def extract_ngrams(self, text: str) -> List[tuple]:
        """Extract n-grams from text string

        Args:
            text (str): completion text

        Returns:
            list: List of n-gram tuples

        TODO: Tokenize text so to reduce memory usage. ie. ('hello','world') -> (324, 531)
        TODO: Replace this with nltk everygram which is more efficient
        """

        if self.preprocess:
            # remove all punctuation
            text = self.preprocess.sub('', text)

        words = self.tokenizer(text.lower())['input_ids'][1:-1]

        if self.word_limit is not None:
            words = words[:self.word_limit]

        ngrams = []
        for i in range(self.n_min, self.n_max + 1):
            ngrams.extend(zip(*[words[j:] for j in range(i)]))

        return ngrams

    def _add_ngrams(self, ngrams: List[tuple]):
        """Adds n-grams to counter, removing old n-grams periodically.
        Counting and pruning method based on Lossy counter.
        Reference: https://files.ifi.uzh.ch/dbtg/sdbs13/T01.3.pdf

        Args:
            ngrams (List[tuple]): List of n-gram tuples
        """

        for ngram in ngrams:
            if ngram in self.counter:
                self.counter[ngram][0] += 1
            else: 
                # Store the tuple (frequence, max_error)
                self.counter[ngram] = [1, self.b_current - 1]
            
            # Start the prune procedure periodically.
            self.num_ngram += 1
            if self.num_ngram % self.window == 0:
                self.b_current = math.ceil(self.num_ngram / self.window) 
                self.prune()
        
        self.num_completion += 1

    def prune(self):
        """Prune the counter when the count is smaller then bucket index.  
        """
        prune_ele = []
        for ele, (frequence, max_error) in self.counter.items():
            if frequence + max_error <= self.b_current:
                prune_ele.append(ele)
        
        for ele in prune_ele:
            del self.counter[ele]  

    def calculate_significance(self) -> dict:
        """Calculate significance of all n-grams in counter. By construction, n-grams with count 1 will have significance 0.

        Returns:
            dict: Dictionary of n-gram tuples and their significance scores
        """

        significance_scores = {}
        for ngram, count in self.counter.items():
            if count[0] + count[1] > max(self.support * self.num_completion, self.b_current + 1):
            # calculate significance score for ngram
                significance_scores[self.tokenizer.decode(ngram)] = self.A ** (len(ngram) - 1) * ((count[0] + count[1]) / self.num_completion) * 100

        self._last_update = self.num_ngram

        return significance_scores

    def get_significance(self) -> dict:
        """Get significance scores, only recalculating if the counter has been updated.

        Returns:
            dict: Dictionary of n-gram tuples and their significance scores
        """

        if self._last_update != self.num_ngram:
            self.significance_scores = self.calculate_significance()

        return self.significance_scores

    def most_common(self, n:int = 10) -> dict:
        """Get most common n-grams in queue

        Args:
            n (int): Number of most common n-grams to return. Defaults to 10.

        Returns:
            dict: Sorted dictionary of n-gram tuples and their counts
        """
        return sorted(self.counter.items(), key=lambda x: x[1][0] + x[1][1], reverse=True)[:n]
         
    
    def most_significant(self, n:int = 10, force_update:bool = True) -> dict:
        """Get most significant n-grams in queue based on significance scores

        Args:
            n (int, optional): Number of most significant n-grams to return. Defaults to 10.
            force_update (bool, optional): Force recalculate the significance scores. Defaults to True.

        Returns:
            dict: Sorted dictionary of n-gram tuples and their significance scores
        """


        scores = self.get_significance() if force_update else self.significance_scores
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]

    def reward(self, prompt: str, completion: str, name: str) -> float:
        """Reward function for blacklist reward model. Returns 1 if completion contains an n-gram with significance above the boundary, 0 otherwise.

        Args:
            prompt (str): Prompt text
            completion (str): Completion text
            name (str): Name of the validation step

        Returns:
            float: Reward value {0,1}
        """

        if completion in prompt:
            return 0.0

        # Get significance scores
        scores = self.get_significance()

        # Check if any n-grams have significance above the boundary
        for ngram, score in scores: 
            if scores.get(ngram) > self.boundary:
                if fuzz.partial_ratio(ngram, completion.lower()) > self.partial_ratio_boundary:
                    return 0

        return 1

    def get_rewards(
        self, prompt: str, completions: List[str], name: str
    ) -> torch.FloatTensor:
        return torch.tensor(
            [self.reward(prompt, completion, name) for completion in completions],
            dtype=torch.float32,
        )

    def normalize_rewards(self, rewards: torch.FloatTensor) -> torch.FloatTensor:
        return rewards
