""" formater """

from collections import OrderedDict

def hooks_output_format(results):
    ''' Format the list to print friendly hooks '''

    output = []
    for result in results:
        output.append(
            OrderedDict(
                [
                    ("Name", result["name"]),
                    ("Description", result["description"]),
                    ("Lifecycle", ", ".join(result["lifecycle"])),
                ]
            )
        )
    return output
