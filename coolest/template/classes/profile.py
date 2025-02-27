__author__ = 'aymgal'

import numpy as np
from typing import Dict

from coolest.template.classes.base import APIBaseObject
from coolest.template.classes.parameter import (Parameter, 
                                                LinearParameter, LinearParameterSet,
                                                NonLinearParameter, HyperParameter)


__all__ = ['Profile' ,'AnalyticalProfile']


class Profile(APIBaseObject):
    """Base class for all mass and light profiles"""

    def __init__(self,
                 documentation: str, 
                 parameters: Dict[(str, Parameter)]) -> None:
        self.type = self.__class__.__name__  # name of children class
        self.documentation = documentation
        self.parameters = parameters
        self.id = None
        super().__init__()


class AnalyticalProfile(Profile):

    def __init__(self,
                 documentation: str, 
                 parameters: Dict[(str, Parameter)]) -> None:
        super().__init__(documentation, parameters=parameters)
        
    def total_num_params(self, include_fixed=False, include_hyper=True):
        count = 0
        for name, parameter in self.parameters.items():
            if isinstance(parameter, (NonLinearParameter, LinearParameter)):
                if not parameter.fixed or include_fixed:
                    count += 1
            elif isinstance(parameter, LinearParameterSet):
                if not parameter.fixed or include_fixed:
                    count += parameter.num_values
            elif isinstance(parameter, HyperParameter) and include_hyper:
                if not parameter.fixed or include_fixed:
                    count += 1
        return count
