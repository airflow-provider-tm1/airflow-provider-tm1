#todo: build the template 
template = {
    'dim': {
        'hierarchy': 'hie_name', 
        'value': 'element',
        'subset_mdx': '{{mdx}}'
    }
}

def compose():
    """
    consume the dictionary, 
    """

    #todo: parse it to subset mdx for each 
    #todo:join them into cube query mdx 

    #? need to validate cube? 
    #! be careful on the ] or any other special character 
    