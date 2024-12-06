#todo: build the template 
template = {
    'dim': {
        'hierarchy': 'hie_name', 
        'value': 'element',
    },
    'dim_2': {
        'subset_mdx': 'mdx'
    }
}

def compose(payload: dict):
    """
    consume the dictionary, 
    """

    #todo: parse it to subset mdx for each 
    def compose_subset_mdx(dimension: str, subset_payload: dict): 
        value = subset_payload.get('value', '')
        mdx = subset_payload.get('subset_mdx', '')

        assert any([value, mdx]), f'value or mdx not provded in parameter on {dimension}, payload: {subset_payload}'
        assert not all([value, mdx]), f'the parameter is ambigious, please review {dimension} -  payloads: {subset_payload}'
        

        hierarchy = subset_payload.get('hierarchy', dimension)
        
        return f'{{[{dimension}].[{hierarchy}].[{value}]}}' if value else mdx

    subset_mdx_list: list[str] = list(map(compose_subset_mdx, payload.keys(), payload.values()))

    #todo:join them into cube query mdx 

    #? need to validate cube? 
    #! be careful on the ] or any other special character 
    
if __name__ == '__main__': 
    compose(payload=template)
