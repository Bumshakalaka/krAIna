Generate a Python docstring in reStructuredText format for the given Python object code. The docstring should include a description of the parameters, the return value without specifying the type, and any raised exceptions. Do not mention the functionality of other functions explicitly unless it is useful to understand the main function. Output Python code with the docstring while keeping the original code intent intact. Do not enclose in markdown tags.

The description should be a maximum of 100 characters. If the description is multi-line, the first line should briefly describe the functionality, while the subsequent lines provide additional details.

Example:
```python
def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    if count == 0:
        raise ZeroDivisionError("Cannot calculate the average of an empty list.")
    return total / count
```

Expected output:
```python
def calculate_average(numbers):
    """
    Calculate the average of a list of numbers.
    
    This function sums the input list and divides by the count of numbers.
    
    :param numbers: List of numerical values.
    :return: The average of the input numbers.
    :raises ZeroDivisionError: If the input list is empty.
    """
    total = sum(numbers)
    count = len(numbers)
    if count == 0:
        raise ZeroDivisionError("Cannot calculate the average of an empty list.")
    return total / count
```

**Instructions:**
- Include a short description of what the function does (max 100 characters).
- If the description is multi-line, the first line should briefly describe the functionality, while the subsequent lines provide additional details.
- Describe the return value without specifying the type.
- Mention any exceptions that the function might raise.
- Do not mention the functionality of other functions explicitly unless it is useful to understand the main function.
- Output Python code with the docstring while keeping the original code intent intact.
- Do not enclose in markdown tags.