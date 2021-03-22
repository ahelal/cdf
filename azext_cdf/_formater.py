from collections import OrderedDict

def hooks_output_format(results):
    output = []
    for result in results:
        output.append(
            OrderedDict([
                    ('Name', result['name']), 
                    ('Descripition', result['descripition']), 
                    ('Lifecycle', ", ".join(result['lifecycle'])),
            ])
        )
    return output
