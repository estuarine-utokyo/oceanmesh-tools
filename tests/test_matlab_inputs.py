from pathlib import Path

from oceanmesh_tools.scan.matlab_inputs import extract_from_text


def test_extract_from_text():
    text = """
    % Generate mesh
    write(m,'TokyoBay');
    A = geodata('dem','tokyodem','shp','coastline_tokyo');
    coastline_main = 'shore/coast.shp';
    dem_primary = 'dem_01.tif';
    """
    meshes, shp, dem = extract_from_text(text)
    assert meshes == ['TokyoBay']
    assert 'coastline_tokyo' in shp
    assert 'shore/coast.shp' in shp
    assert 'tokyodem' in dem
    assert 'dem_01.tif' in dem

