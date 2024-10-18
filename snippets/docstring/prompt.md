Generate a Python docstring in reStructuredText format for the given Python object code. The docstring should include:

- A brief description of the function (maximum 100 characters).
  - If multi-line, the first line should briefly describe the functionality, with subsequent lines providing more details.
- A description of the parameters.
- A description of the return value (without specifying the type).
- Any raised exceptions.

**Instructions**:
- Do not mention the functionality of other functions explicitly unless it is useful to understand the main function.
- Output the Python code with the docstring while keeping the original code intent intact.
- Format the output as Markdown code.
- be consisted, do not add sentence starts with: Here is, certainly, hello. I need only Python code with docstring

**Example**:

Python Code:
def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    if count == 0:
        raise ZeroDivisionError("Cannot calculate the average of an empty list.")
    return total / count

Expected Output:
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