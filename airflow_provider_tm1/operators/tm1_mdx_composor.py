#todo: build the template 
import pytest

template = {
    'dim': {
        'hierarchy': 'hie_name', 
        'value': 'element',
    },
    'dim_2': {
        'subset_mdx': 'mdx'
    }
}

def compose(cube_name, payload: dict):
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
        
        #! be careful on the ] or any other special character 
        #* https://www.ibm.com/docs/en/planning-analytics/2.0.0?topic=reports-naming-conventions
        dimension = value.replace(']', ']]')        
        hierarchy = hierarchy.replace(']', ']]')
        value = value.replace(']', ']]')
        
        return f'{{[{dimension}].[{hierarchy}].[{value}]}}' if value else mdx

    subset_mdx_list: list[str] = list(map(compose_subset_mdx, payload.keys(), payload.values()))

    #todo:join them into cube query mdx
    if len(subset_mdx_list) == 1: 
        raise ValueError('by TM1 cube design, the cube with single diemnsion is not exists')
    
    rows, columns = subset_mdx_list[0], subset_mdx_list[1:]
    mdx = f'SELECT {rows} ON ROWS, {" * ".join(columns)} ON COLUMNS FROM [{cube_name}]'

    return mdx
    #? need to validate cube? 


def test_compose_normal_query_with_two_dimensions():
    payload = {
        'dim': {
            'hierarchy': 'hie_name', 
            'value': 'element',
        },
        'dim_2': {
            'subset_mdx': '{{TM1SubsetAll([dim_2].[hie_name])}}'
        }
    }

    test_result = compose('Cube', payload)
    expected_value = 'SELECT {[dim].[hie_name].[element]} ON ROWS,  {{TM1SubsetAll([dim_2].[hie_name])}}  ON COLUMNS FROM [Cube]'

    assert test_result == expected_value, f'expected: {expected_value}, got: {test_result}'
    
def test_compose_with_single_dimensions():
    payload = {
        'dim': {
            'hierarchy': 'hie_name', 
            'value': 'element',
        }
    }

    with pytest.raises(ValueError) as excinfo:
        compose('Cube', payload)
    
    assert str(excinfo.value) == 'by TM1 cube design, the cube with single diemnsion is not exists'
    
def test_compose_with_ambigious_payload():
    payload = {
        'dim': {
            'hierarchy': 'hie_name', 
            'value': 'element',
            'subset_mdx': '{{TM1SubsetAll([dim_2].[hie_name])}}'
        }
    }

    with pytest.raises(AssertionError) as excinfo:
        compose('Cube', payload)
    
    assert str(excinfo.value) == 'the parameter is ambigious, please review dim -  payloads: {\'hierarchy\': \'hie_name\', \'value\': \'element\', \'subset_mdx\': \'{{TM1SubsetAll([dim_2].[hie_name])}}\'}'
    
def test_compose_with_missing_value_and_mdx():
    payload = {
        'dim': {
            'hierarchy': 'hie_name'
        }
    }

    with pytest.raises(AssertionError) as excinfo:
        compose('Cube', payload)
    
    assert str(excinfo.value) == "value or mdx not provded in parameter on dim, payload: {'hierarchy': 'hie_name'}"
    
def test_compose_with_mdx_only():
    payload = {
        'dim': {
            'subset_mdx': '{{TM1SubsetAll([dim].[hie_name])}}'
        },
        'dim_2': {
            'subset_mdx': '{{TM1SubsetAll([dim_2].[hie_name])}}'
        }
    }

    test_result = compose('Cube', payload)
    expected_value = 'SELECT  {{TM1SubsetAll([dim].[hie_name])}}  ON ROWS,  {{TM1SubsetAll([dim_2].[hie_name])}}  ON COLUMNS FROM [Cube]'

    assert test_result == expected_value, f'expected: {expected_value}, got: {test_result}'

def test_compose_with_special_character():
    payload = {
        'dim': {
            'hierarchy': 'hie_name', 
            'value': 'element]',
        },
        'dim_2': {
            'subset_mdx': '{{TM1SubsetAll([dim_2].[hie_name])}}'
        }
    }

    test_result = compose('Cube', payload)
    expected_value = 'SELECT {[dim].[hie_name].[element]]} ON ROWS,  {{TM1SubsetAll([dim_2].[hie_name])}}  ON COLUMNS FROM [Cube]'

    assert test_result == expected_value, f'expected: {expected_value}, got: {test_result}'

if __name__ == '__main__': 
    print(compose(cube_name='Cube', payload=template))
