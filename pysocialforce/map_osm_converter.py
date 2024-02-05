"""
map_osm_converter.py
This script is used to convert the SVG file generated by OpenStreetMap
to a new SVG file that contains only the buildings.
"""

import xml.etree.ElementTree as ET
import time
import re
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_buildings_as_obstacle(
        map_full_name,
        building_rgb_color_str:str = 'rgb(85.098039%,81.568627%,78.823529%)',
        map_scale_factor:float = 5000):
    """
    Extracts the buildings from the SVG file and saves them to a new SVG file.
    Args:
    map_full_name (str): The full path to the SVG file.
    building_rgb_color_str (str): The color to filter by (in percentage format).
    map_scale_factor (float): The scale factor applied during the export.
        !!!Tehere is uncertainty in this scale factor!!!
    """
    logger.info("Converting Map: %s", map_full_name)
    tree = ET.parse(map_full_name)
    root = tree.getroot()

    # The scale factor applied during the export
    scale_factor =  map_scale_factor/1350 * 1/4.08 # TODO: Replace this with the actual scale factor
    logger.debug("Scale factor: %s", scale_factor)

    # Identify all elements with the specified color
    # Initialize an empty list to store the elements
    elements = []
    # Iterate over all elements in the root object
    for elem in root.iter():
    # Check if the element has a 'style' attribute and if the 'style' attribute
    # contains the building_rgb_color_str
        if 'style' in elem.attrib and building_rgb_color_str in elem.attrib['style']:
        # If the condition is met, add the element to the list
            elements.append(elem)


    # Create a new SVG file with just the elements
    new_root = ET.Element('svg', xmlns="http://www.w3.org/2000/svg")

    # Copy viewBox attribute from the original root to the new root

    if 'viewBox' in root.attrib:
        viewbox = list(map(float, root.attrib['viewBox'].split()))
        logger.debug("old viewbox: %s", viewbox)
        viewbox[2] *= scale_factor  # Scale the width
        viewbox[3] *= scale_factor  # Scale the height
        logger.debug("new viewbox: %s", viewbox)
        new_root.attrib['viewBox'] = ' '.join(map(str, viewbox))

    for elem in elements:
    # Check if the element is a path
        if elem.tag.endswith('path'):
            # Parse the d attribute
            d = elem.attrib['d']
            commands = re.findall(r'([A-Za-z])|(-?\d+(?:\.\d+)?)', d)

            # Scale the coordinates
            scaled_commands = []
            for command in commands:
                if command[0]:  # If it's a command
                    scaled_commands.append(command[0])
                else:  # If it's a coordinate
                    scaled_commands.append(str(float(command[1]) * scale_factor))

            # Reassemble the d attribute
            elem.attrib['d'] = ' '.join(scaled_commands)
            elem.attrib['{http://www.inkscape.org/namespaces/inkscape}label'] = 'obstacle'

        new_root.append(elem)

    # raise an error if elements is empty
    if len(elements) == 0:
        raise ValueError('No elements found with color ' + building_rgb_color_str)

    return new_root

def add_scale_bar_to_root(root: ET.Element, line_length: int = 100):
    """
    Adds a scale bar to the root element of an SVG image.

    Parameters:
        root (ET.Element): The root element of the SVG image.
        line_length (int): The length of each line segment in meters.

    Returns:
        ET.Element: The modified root element with the scale bar added.
    """
    # Get the width of the image
    viewbox = list(map(float, root.attrib['viewBox'].split()))
    image_width = viewbox[2]

    # Add an alternating black and white line over the whole image width
    line_length = 100  # Length of each line segment in meters
    for i in range(0, int(image_width), line_length):
        color = "rgb(0,0,0)" if (i // line_length) % 2 == 0 else "rgb(100%,100%,100%)"
        ET.SubElement(
            root,
            'line', 
            x1=str(i),
            y1="10",
            x2=str(i + line_length),
            y2="10",
            style=f"stroke:{color};stroke-width:2"
            )
    scale_text = ET.SubElement(root, 'text', x="10", y="30", style="font-size:12px")
    # Replace this with the actual distance the scale bar represents
    scale_text.text = str(line_length) + " m"

    return root

def save_root_as_svg(root: ET.Element, filename: str, add_conversion_time: bool = False):
    """
    Saves the root element as an SVG file.

    Parameters:
        root (ET.Element): The root element of the SVG image.
        filename (str): The name of the SVG file to save. Include `.svg` in the name.
        add_conversion_time (bool): Whether to add the current time to the filename.
    """
    tree = ET.ElementTree(root)
    if add_conversion_time:
        now = time.strftime("%Y%m%d-%H%M%S")
        filename = filename.replace('.svg', f'_{now}.svg')
    tree.write(filename)
    logger.info("Saving the new SVG file: %s", filename)
