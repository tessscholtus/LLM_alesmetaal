# src/xml_generator.py (or integrate into main processing)
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json # For pretty printing if needed

def generate_xml(normalized_data):
    """
    Generates an XML string from the normalized data, including Dimensions.
    The structure of the XML will depend on your order system's requirements.
    This is a generic example.
    """
    if not normalized_data:
        return None

    root = ET.Element("OrderData") # Your root element name might differ

    # Add fields that are single values
    single_value_fields = [
        "drawing_number", "revision", "part_title", "part_description",
        "company_name", "welding_designation", "weld_finish",
        "post_treatment", "material_grade", "drawing_date", "scale"
    ]
    for key in single_value_fields:
        value = normalized_data.get(key)
        if value not in (None, ""):
            ET.SubElement(root, key).text = str(value)

    # Add Notes (list of strings)
    notes = normalized_data.get("notes")
    if notes:
        notes_element = ET.SubElement(root, "Notes")
        for note in notes:
            ET.SubElement(notes_element, "Note").text = str(note)

    # Add Dimensions (list of dicts)
    dimensions = normalized_data.get("dimensions")
    if dimensions:
        dims_element = ET.SubElement(root, "Dimensions")
        for dim in dimensions:
            dim_element = ET.SubElement(dims_element, "Dimension")
            # Ensure keys match what you expect in XML
            ET.SubElement(dim_element, "Value").text = str(dim.get("value"))
            ET.SubElement(dim_element, "Unit").text = str(dim.get("unit"))
            ET.SubElement(dim_element, "Description").text = str(dim.get("description"))


    # Add Tolerances_Table
    tolerances_table = normalized_data.get("tolerances_table")
    if tolerances_table and tolerances_table.get("bands"):
        tt_element = ET.SubElement(root, "TolerancesTable")
        ET.SubElement(tt_element, "Unit").text = tolerances_table.get("unit", "mm")
        bands_element = ET.SubElement(tt_element, "Bands")
        for band_key, tol_value in tolerances_table["bands"].items():
            band_element = ET.SubElement(bands_element, "Band")
            band_element.set("range", band_key) # Use attribute for range
            band_element.text = str(tol_value)

    # Add General Tolerances if separate
    general_tolerance = normalized_data.get("tolerances_general")
    if general_tolerance:
        ET.SubElement(root, "TolerancesGeneral").text = str(general_tolerance)


    # Pretty print the XML
    xml_string = ET.tostring(root, encoding='utf-8')
    parsed_string = minidom.parseString(xml_string)
    pretty_xml = parsed_string.toprettyxml(indent="  ")

    return pretty_xml

# Example usage:
# order_xml = generate_xml(normalized_data)
# if order_xml:
#     print(order_xml)