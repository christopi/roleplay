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
import torch
import bittensor as bt
from enum import Enum
from typing import List
from abc import ABC, abstractmethod
from prompting.validators.tasks import Task


class BasePenaltyModel(ABC):
    def __init__(self, max_penalty: float):
        self.max_penalty = max_penalty

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    def __str__(self) -> str:
        return str(self.name)

    def __repr__(self) -> str:
        return str(self.name)

    @abstractmethod
    def calculate_penalties(task: Task, completions: List[str]) -> torch.FloatTensor:
        ...

    def apply_penalties(
        self, responses: List[bt.Synapse], task: Task
    ) -> torch.FloatTensor:
        completions = [response.completion for response in responses]
        raw_penalties = self.calculate_penalties(task, completions)

        # Copy raw penalties to a new tensor for adjustments
        adjusted_penalties = raw_penalties.clone()

        # If accumulated penalties are bigger than 1, set them to 1
        mask_greater_or_equal_1 = adjusted_penalties >= 1
        adjusted_penalties[mask_greater_or_equal_1] = 1

        # Adjust values greater than max_penalty
        mask_greater_than_max_penalty = adjusted_penalties > self.max_penalty
        adjusted_penalties[mask_greater_than_max_penalty] = self.max_penalty

        # Invert penalties to scale rewards accordingly
        applied_penalties = 1 - adjusted_penalties

        return raw_penalties, adjusted_penalties, applied_penalties


class PenaltyModelType(Enum):
    task_validation_penalty = "task_validation_penalty"
    keyword_match_penalty = "keyword_match_penalty"
    sentence_length_penalty = "sentence_length_penalty"
