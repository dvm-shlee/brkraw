"""Provides parsing utilities for handling and converting parameter data from string representations to structured formats.

This module includes the `Parser` class, which leverages regular expressions to accurately parse and convert various 
data types found in parameter files, such as integers, floats, complex arrays, and strings. 
The functionality is designed to support the manipulation and analysis of data from Paravision parameter files, 
ensuring data integrity and accessibility.

Classes:
    Parser: A class that offers a comprehensive suite of methods for parsing parameter data, 
            supporting complex data structures and providing tools to convert and clean data efficiently.
"""

import re
import numpy as np
from collections import OrderedDict, defaultdict
from copy import copy

# REGEX patterns
ptrn_param          = r'^\#\#(?P<key>.*)\=(?P<value>.*)$'
ptrn_key            = r'^\$(?P<key>.*)'
ptrn_array          = r"\((?P<array>[^()]*)\)"
ptrn_complex_array  = r"\((?P<comparray>\(.*)\)$"
ptrn_comment        = r'\$\$.*'
ptrn_float          = r'^-?\d+\.\d+$'
ptrn_engnotation    = r'^-?[0-9.]+e-?[0-9.]+$'
ptrn_integer        = r'^[-]*\d+$'
ptrn_string         = r'^\<(?P<string>[^>]*)\>$'
ptrn_arraystring    = r'\<(?P<string>[^>]*)\>[,]*'
ptrn_bisstring      = r'\<(?P<string>\$Bis[^>]*)\#\>'
ptrn_braces         = r'\((?P<contents>[^()]*)\)'
# Paravision 360 related. @[number of repititions]([number]) ex) @5(0)
ptrn_at_array       = r'@(\d*)\*\(([-]?\d*[.]?\d*[eE]?[-]?\d*?)\)'

# Conditional enum
HEADER = 0
PARAMETER = 1


class Parser: 
    """A utility class for parsing and converting parameter data from string representations.

    The Parser class uses regular expressions to identify and convert data types found in parameter files. It handles typical data formats including integers, floats, strings, and complex arrays, making them amenable for further processing and analysis.

    Methods:
        load_param(stringlist): Parses parameters from a list of strings, identifying headers and parameters.
        convert_string_to(string): Converts strings to appropriate data types based on their content.
        clean_up_elements_in_array(data): Cleans array elements by handling patterns and replacing them with repeated values.
        process_complexarray(data): Converts complex nested array strings into structured dictionary formats.
        parse_shape(shape): Interprets textual shape descriptions into tuple or list formats.
        parse_data(data): Converts string data into lists or single values depending on the structure.
        convert_data_to(data, shape): Transforms data into the specified shape or data type.
    """
    @staticmethod
    def load_param(stringlist):
        """Parses parameters from a list of string representations of a JCAMP DX file.

        Each string is inspected for key-value pairs that represent parameters or headers. 
        This method categorizes and stores them accordingly.

        Args:
            stringlist (list[str]): A list of strings, each containing a line from a JCAMP DX file.

        Returns:
            tuple: A tuple containing an OrderedDict of parameters, a list of line numbers where parameters are found, and the original list of strings.
        """
        params = OrderedDict()
        param_addresses = []
        compiled_ptrn_param = re.compile(ptrn_param)
        compiled_ptrn_key = re.compile(ptrn_key)

        for line_num, line in enumerate(stringlist):
            if regex_obj := compiled_ptrn_param.match(line):
                key = regex_obj['key']
                value = regex_obj['value']
                if compiled_ptrn_key.match(key):
                    key = re.sub(ptrn_key, r'\g<key>', key)
                    params[line_num] = (PARAMETER, key, value)
                else:
                    params[line_num] = (HEADER, key, value)
                param_addresses.append(line_num)
        return params, param_addresses, stringlist


    @staticmethod
    def convert_string_to(string):
        """Converts a string to an integer, float, or string based on its content, using regular expression matching.

        Args:
            string (str): The string to be converted.

        Returns:
            int, float, str, or None: The converted value of the string, or None if the string is empty.
        """
        string = string.strip()
        if re.match(ptrn_string, string):
            string = re.sub(ptrn_string, r'\g<string>', string)
        if not string:
            return None
        if re.match(ptrn_float, string) or re.match(ptrn_engnotation, string):
            return float(string)
        elif re.match(ptrn_integer, string):
            return int(string)
        return string

    @staticmethod
    def clean_up_elements_in_array(data):
        """Cleans up array elements by replacing patterns with repeated values.

        Args:
            elements (list): A list of array elements with patterns.

        Returns:
            list: The cleaned up array elements.
        """
        elements = re.findall(ptrn_at_array, data)
        elements = list(set(elements))
        for str_ptn in elements:
            num_cnt = int(str_ptn[0])
            num_repeat = float(str_ptn[1])
            str_ptn = f"@{str_ptn[0]}*({str_ptn[1]})"

            str_replace_old = str_ptn
            str_replace_new = [num_repeat for _ in range(num_cnt)]
            str_replace_new = str(str_replace_new)
            str_replace_new = str_replace_new.replace(",", "")
            str_replace_new = str_replace_new.replace("[", "")
            str_replace_new = str_replace_new.replace("]", "")
            data = data.replace(str_replace_old, str_replace_new)
        return data

    @staticmethod
    def process_bisarray(elements, shape):
        """Determines the case of an array with BIS prefix by converting each element to a specific data type.

        Args:
            elements (list): A list of elements representing a bisarray.

        Returns:
            float, int, or list: The converted elements of the bisarray. If there is only one element, it is returned as is, otherwise a list of converted elements is returned.
        """
        elements = [Parser.convert_string_to(c) for c in elements]
        elements = elements.pop() if len(elements) == 1 else elements
        if isinstance(shape, list) and shape[0] == len(elements):
            elements = [e.split(',') for e in elements]
        return elements

    @staticmethod
    def process_complexarray(data):
        """Processes a string representation of a complex nested array and converts it into a structured dictionary format.

        Args:
            data (str): The complex array string to be processed.

        Returns:
            dict: A dictionary representing the structured levels of the array, categorized by depth.
        """
        data_holder = copy(data)
        parser = defaultdict(list)
        level = 1
        while re.search(ptrn_braces, data_holder):
            for parsed in re.finditer(ptrn_braces, data_holder):
                cont_parser = [Parser.convert_data_to(cont.strip(), -1) for cont in parsed.group('contents').split(',') if Parser.convert_data_to(cont.strip(), -1) is not None]
                parser[f'level_{level}'].append(cont_parser)
            data_holder = re.sub(ptrn_braces, '', data_holder)
            level += 1
        return dict(parser)
    
    @staticmethod
    def process_string(data, shape):
        """Process a string and return the parsed data based on its shape.

        Args:
            data: The string to be processed.
            shape: The shape of the data.

        Returns:
            tuple: A tuple containing the parsed data and an empty string, or the processed string.
        """
        shape = Parser.parse_shape(shape)
        if elements := re.findall(ptrn_bisstring, data):
            data = Parser.process_bisarray(elements, shape)
            return data, -1
        else:
            data = Parser.clean_up_elements_in_array(data)
        if re.match(ptrn_complex_array, data):
            data = Parser.process_complexarray(data)
        elif re.match(ptrn_string, data):
            data = re.sub(ptrn_string, r'\g<string>', data)
        else:
            data = Parser.parse_data(data)
        return data, shape

    @staticmethod
    def parse_shape(shape):
        """Parse the shape of the data.

        Args:
            shape: The shape of the data.

        Returns:
            str: The parsed shape.

        Raises:
            ValueError: If the shape is invalid.
        """
        if shape != -1:
            shape = re.sub(ptrn_array, r'\g<array>', shape)
            if ',' in shape:
                return [Parser.convert_string_to(c) for c in shape.split(',')]
        return shape

    @staticmethod
    def parse_data(data):
        """Parse the data based on its format.

        Args:
            data: The data to be parsed.

        Returns:
            list or str: The parsed data.
        """
        if matched := re.findall(ptrn_array, data):
            return Parser.parse_array_data(matched)
        elif ',' in data:
            return [Parser.convert_string_to(c) for c in data.split(',')]
        elif ' ' in data:
            return [Parser.convert_string_to(c) for c in data.split(' ')]
        return data

    @staticmethod
    def parse_array_data(matched):
        """Parse the array data.

        Args:
            matched: A list of strings representing the matched array data.

        Returns:
            list: The parsed array data.
        """
        if any(',' in cell for cell in matched):
            return [[Parser.convert_string_to(c) for c in cell.split(',')] for cell in matched]
        return [Parser.convert_string_to(c) for c in matched]

    @staticmethod
    def convert_data_to(data, shape):
        """Convert the given data to the specified shape.

        Args:
            data: The data to be converted.
            shape: The desired shape of the data.

        Returns:
            object: The converted data.
        """
        if isinstance(data, str):
            data, shape = Parser.process_string(data, shape)
        if isinstance(data, list):
            if (
                isinstance(shape, list)
                and not any(isinstance(c, str) for c in data)
                and all(c is not None for c in data)
            ):
                data = np.asarray(data).reshape(shape)
        elif isinstance(data, str):
            data = Parser.convert_string_to(data)
        return data
