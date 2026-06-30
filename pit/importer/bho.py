# -*- coding: utf-8 -*-
"""
BHO File Generator Class
Generates .bho (Bond Output) files for RICS API selective outputs
# MBS has different member names for the same output type
# Duration output only for Bond/AmortizingBond
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Optional
import os


class BHOFileGenerator:
    """
    Class to generate .bho files for RICS API selective outputs.
    
    Example usage:
        generator = BHOFileGenerator(
            output_type="TotalValue",
            bond_ids=["11_AAFHHCCAPITALLLC.00032@AA8SIGI", "8_AAGFHUKPLC.00033GAA3"]
        )
        generator.generate("Bonds_TV.bho", "Bond_TotalValue.csv")
    """
    
    # Default XML attributes
    OUTPUT_VERSION = "10.4.0.0"
    CULTURE = "en-US"
    LIST_SEPARATOR = ","
    DECIMAL_POINT = "."
    SHORT_DATE_PATTERN = "M/d/yyyy"
    LONG_TIME_PATTERN = "h:mm:ss tt"
    
    # Default format attributes
    FORMAT_TYPE = "TrialTimestep"
    NUMBER_FORMAT = "0.0000"
    SHOULD_IGNORE_TIMESTEP_ZERO = "False"
    IS_ASYMMETRIC_OUTPUT = "False"
    PERIOD = "1"
    HEADER_COLS = "True"
    HEADER = "True"
    
    # Mapping of output types to member names for parameter ID
    # for GC, GCPD, GCCRE, GCRETAIL, GCCREPD, GCRETAILPD
    OUTPUT_TYPE_MAPPING = {
        "CreditClass": "CreditClass",
        "DefaultFlag": "DefaultFlag",
        "TotalValue": "RolledUpTotalValue",
        "Price": "Price",
        "Interest": "Interest",
        "Principal": "Principal",
        "Recovery": "Recovery",
        'TotalReturn': 'TotalReturn',
        'TotalReturnIndex': 'TotalReturnIndex',
    }
    
    # Mapping of output types to member names for MBS parameter ID (Agency MBS)
    OUTPUT_TYPE_MAPPING_MBS = {
        "Price": "Price",
        "Interest": "Interest",
        "Principal": "Principal",
        'TotalReturn': 'TotalReturn',
        'TotalReturnIndex': 'TotalReturnIndex',
    }
    
    # Mapping of output types to member attribute values for non-MBS
    # This is used for the "member" attribute in the BHO file
    MEMBER_NAME_MAPPING = {
        "CreditClass": "CreditClass",
        "DefaultFlag": "DefaultFlag",
        "TotalValue": "RolledUpTotalValue",
        "Price": "Price",
        "Interest": "Interest.Value",
        "Principal": "Principal.Value",
        "Recovery": "Recovery.Value",
        'TotalReturn': 'TotalReturn',
        'TotalReturnIndex': 'TotalReturnIndex.Value',
    }
    
    # Mapping of output types to member attribute values for MBS (Agency MBS)
    # This is used for the "member" attribute in the BHO file
    MEMBER_NAME_MAPPING_MBS = {
        "Price": "PriceOutput",
        "Interest": "InterestPrime",
        "Principal": "PrincipalPrime",
        'TotalReturn': 'TotalReturn.Value',
        'TotalReturnIndex': 'TotalReturnIndex.Value',
    }
    
    def __init__(
        self,
        output_type: str,
        bond_ids: List[str],
        output_version: Optional[str] = None,
        number_format: Optional[str] = None,
        mbs_identifiers: Optional[set] = None
    ):
        """
        Initialize the BHO File Generator.
        
        Args:
            output_type: The type of output (e.g., "TotalValue", "CreditClass", "DefaultFlag")
            bond_ids: List of bond identifiers (e.g., ["11_AAFHHCCAPITALLLC.00032@AA8SIGI"])
            output_version: Optional version override (default: "10.4.0.0")
            number_format: Optional number format override (default: "0.0000")
            mbs_identifiers: Optional set of MBS identifiers. If provided, MBS-specific mappings
                           will be used for those identifiers. Allows mixed MBS and non-MBS
                           identifiers in the same BHO file.
        """
        self.output_type = output_type
        self.bond_ids = bond_ids
        self.output_version = output_version or self.OUTPUT_VERSION
        self.number_format = number_format or self.NUMBER_FORMAT
        self.mbs_identifiers = mbs_identifiers or set()
        
        # Get the default member name from the output type (for non-MBS)
        self.parameter_member_name = self.OUTPUT_TYPE_MAPPING.get(
            output_type, 
            output_type  # Use output_type as fallback if not in mapping
        )
        self.member_name = self.MEMBER_NAME_MAPPING.get(
            output_type,
            output_type  # Use output_type as fallback if not in mapping
        )
    
    def _create_parameter_element(self, bond_id: str) -> ET.Element:
        """
        Create a parameter element for a given bond ID.
        Uses MBS-specific mapping if the bond_id is in mbs_identifiers, otherwise uses default mapping.
        
        Args:
            bond_id: The bond identifier
            
        Returns:
            ET.Element: The parameter XML element
        """
        # Determine which mapping to use based on whether this is an MBS identifier
        if bond_id in self.mbs_identifiers:
            # Use MBS-specific mapping for parameter ID
            parameter_member_name = self.OUTPUT_TYPE_MAPPING_MBS.get(
                self.output_type,
                self.output_type  # Fallback to output_type if not in MBS mapping
            )
            # Use MBS-specific mapping for member attribute
            member_name = self.MEMBER_NAME_MAPPING_MBS.get(
                self.output_type,
                self.output_type  # Fallback to output_type if not in MBS mapping
            )
        else:
            # Use default mapping for parameter ID
            parameter_member_name = self.parameter_member_name
            # Use default mapping for member attribute
            member_name = self.member_name
        
        parameter_id = f"RICS.Assets.GranularCounterparties.{bond_id}.{parameter_member_name}"
        
        parameter = ET.Element("parameter")
        parameter.set("id", parameter_id)
        parameter.set("member", member_name)
        parameter.set("type", "Output")
        parameter.set("name", parameter_id)
        
        
        if bond_id in self.mbs_identifiers:
            if parameter_member_name in ["TotalReturn"]:
                input_elem = ET.SubElement(parameter, "input")
                input_elem.set("type", "FilePeriod")
                input_elem.set("data_type", "Integer")
        else:
            if parameter_member_name in ["Interest", "Principal", "Recovery", "TotalReturn"]:
                input_elem = ET.SubElement(parameter, "input")
                input_elem.set("type", "FilePeriod")
                input_elem.set("data_type", "Integer")
        
        return parameter
    
    def _create_format_element(self) -> ET.Element:
        """
        Create the format element with default attributes.
        
        Returns:
            ET.Element: The format XML element
        """
        format_elem = ET.Element("format")
        format_elem.set("type", self.FORMAT_TYPE)
        format_elem.set("folder", "")
        format_elem.set("number_format", self.number_format)
        format_elem.set("shouldIgnoreTimestepZero", self.SHOULD_IGNORE_TIMESTEP_ZERO)
        format_elem.set("isAsymmetricOutput", self.IS_ASYMMETRIC_OUTPUT)
        format_elem.set("period", self.PERIOD)
        format_elem.set("headercols", self.HEADER_COLS)
        format_elem.set("header", self.HEADER)
        format_elem.set("trialHeaderLabel", "")
        format_elem.set("timestepHeaderLabel", "")
        format_elem.set("parameterHeaderLabel", "")
        format_elem.set("futureScenarioPrefix", "")
        format_elem.set("historicScenarioPrefix", "")
        format_elem.set("mappingFile", "")
        format_elem.set("meta_risk_economy", "")
        format_elem.set("meta_risk_loss_given_default", "")
        format_elem.set("meta_risk_additional_headers", "")
        
        return format_elem
    
    def _create_file_element(self, csv_filename: str) -> ET.Element:
        """
        Create the file element with format and parameters.
        
        Args:
            csv_filename: Name of the output CSV file
            
        Returns:
            ET.Element: The file XML element
        """
        file_elem = ET.Element("file")
        file_elem.set("src", csv_filename)
        file_elem.set("disabled", "False")
        
        # Add format element
        format_elem = self._create_format_element()
        file_elem.append(format_elem)
        
        # Add parameter elements for each bond ID
        for bond_id in self.bond_ids:
            parameter_elem = self._create_parameter_element(bond_id)
            file_elem.append(parameter_elem)
        
        return file_elem
    
    def _create_root_element(self, csv_filename: str) -> ET.Element:
        """
        Create the root output element.
        
        Args:
            csv_filename: Name of the output CSV file
            
        Returns:
            ET.Element: The root XML element
        """
        root = ET.Element("output")
        root.set("version", self.output_version)
        root.set("culture", self.CULTURE)
        root.set("list_separator", self.LIST_SEPARATOR)
        root.set("decimal_point", self.DECIMAL_POINT)
        root.set("short_date_pattern", self.SHORT_DATE_PATTERN)
        root.set("long_time_pattern", self.LONG_TIME_PATTERN)
        
        # Add file element
        file_elem = self._create_file_element(csv_filename)
        root.append(file_elem)
        
        return root
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """
        Return a pretty-printed XML string for the Element.
        
        Args:
            elem: The root XML element
            
        Returns:
            str: Pretty-printed XML string
        """
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def generate(
        self,
        output_filename: str,
        csv_filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Generate the .bho file.
        
        Args:
            output_filename: Name of the output .bho file (e.g., "Bonds_TV.bho")
            csv_filename: Optional name of the CSV file referenced in the .bho file.
                         If None, will be derived from output_filename.
            output_dir: Optional directory to save the file. If None, uses current directory.
            
        Returns:
            str: Path to the generated file
        """
        # Generate CSV filename if not provided
        if csv_filename is None:
            # Remove .bho extension and add appropriate suffix
            base_name = os.path.splitext(output_filename)[0]
            if self.output_type == "CreditClass":
                csv_filename = "Counterparty_CreditClassIndex.csv"
            elif self.output_type == "DefaultFlag":
                csv_filename = "Counterparty_DefaultFlag.csv"
            else:
                csv_filename = f"Bond_{self.output_type}.csv"
        
        # Create root element
        root = self._create_root_element(csv_filename)
        
        # Generate XML string
        xml_string = self._prettify_xml(root)
        
        # Remove the XML declaration line added by minidom
        lines = xml_string.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        xml_string = '\n'.join(lines).strip()
        
        # Determine output path
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
        else:
            output_path = output_filename
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_string)
        
        return output_path
    
    def generate_string(self, csv_filename: Optional[str] = None) -> str:
        """
        Generate the .bho file content as a string without writing to file.
        
        Args:
            csv_filename: Optional name of the CSV file referenced in the .bho file.
                         If None, will use a default based on output_type.
            
        Returns:
            str: The XML content as a string
        """
        # Generate CSV filename if not provided
        if csv_filename is None:
            if self.output_type == "CreditClass":
                csv_filename = "Counterparty_CreditClassIndex.csv"
            elif self.output_type == "DefaultFlag":
                csv_filename = "Counterparty_DefaultFlag.csv"
            else:
                csv_filename = f"Bond_{self.output_type}.csv"
        
        # Create root element
        root = self._create_root_element(csv_filename)
        
        # Generate XML string
        xml_string = self._prettify_xml(root)
        
        # Remove the XML declaration line added by minidom
        lines = xml_string.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        xml_string = '\n'.join(lines).strip()
        
        return xml_string

