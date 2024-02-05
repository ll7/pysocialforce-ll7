"""extract the information of the path in the svg file generated by InkScape"""
import xml.etree.ElementTree as ET
import re
import logging
import numpy as np

logger = logging.getLogger(__name__)

def svg_path_info(svg_file):
    """
    Extracts path information from an SVG file.
    
    returns a list of dictionaries, each containing the following keys:
    - 'coordinates': a numpy array of shape (n, 2) containing the x and y coordinates
    - 'label': the 'inkscape:label' attribute of the path
    - 'id': the 'id' attribute of the path
    """
    logger.info("Extracting path information from: %s", svg_file)

    # Parse the SVG file
    svg_tree = ET.parse(svg_file)
    svg_root = svg_tree.getroot()

    # Define the SVG and Inkscape namespaces
    namespaces = {
        'svg': 'http://www.w3.org/2000/svg',
        'inkscape': 'http://www.inkscape.org/namespaces/inkscape'
    }

    # Find all 'path' elements in the SVG file
    paths = svg_root.findall('.//svg:path', namespaces)

    # Initialize an empty list to store the path information
    path_info = []

    # Compile the regex pattern for performance
    coordinate_pattern = re.compile(r"([+-]?[0-9]*\.?[0-9]+)[, ]([+-]?[0-9]*\.?[0-9]+)")

    # Iterate over each 'path' element
    for path in paths:
        # Extract the 'd' attribute (coordinates), 'inkscape:label' and 'id'
        input_string = path.attrib.get('d')
        if not input_string:
            continue  # Skip paths without the 'd' attribute

        label = path.attrib.get('{http://www.inkscape.org/namespaces/inkscape}label')
        id_ = path.attrib.get('id')

        # Find all matching coordinates
        filtered_coordinates = coordinate_pattern.findall(input_string)
        if not filtered_coordinates:
            logger.warning("No coordinates found for path: %s", id_)
            continue

        # Convert the matched strings directly into a numpy array of floats
        np_coordinates = np.array(filtered_coordinates, dtype=float)

        # Append the information to the list
        path_info.append({'coordinates': np_coordinates, 'label': label, 'id': id_})

    return path_info