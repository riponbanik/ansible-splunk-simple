import logging
from xml.dom.minidom import Document
import xml.dom
import xml.sax.saxutils
import sys
import re
import os
import hashlib
import json
import time

from splunk.appserver.mrsparkle.lib.util import make_splunkhome_path
sys.path.append(make_splunkhome_path(["etc", "apps", "SA-Utils", "lib"]))
from SolnCommon import log

# Define logger using the name of the script here, versus in the modular_input class.
logger = log.setup_logger(name='python_modular_input', level=logging.INFO)


class FieldValidationException(Exception):
    pass


class Field(object):
    """
    This is the base class that should be used to for field validators. Sub-class this and override to_python if you need custom validation.
    """
    
    DATA_TYPE_STRING = 'string'
    DATA_TYPE_NUMBER = 'number'
    DATA_TYPE_BOOLEAN = 'boolean'
    
    def get_data_type(self):
        """
        Get the type of the field.
        """
        
        return Field.DATA_TYPE_STRING 
    
    def __init__(self, name, title, description, required_on_create=True, required_on_edit=False):
        """
        Create the field.
        
        Arguments:
        name -- Set the name of the field (e.g. "database_server")
        title -- Set the human readable title (e.g. "Database server")
        description -- Set the human readable description of the field (e.g. "The IP or domain name of the database server")
        required_on_create -- If "true", the parameter is required on input stanza creation.
        required_on_edit -- If "true", the parameter is required on input stanza modification.

        Default values for required_on_create and required_on_edit match the
        documented behavior at http://docs.splunk.com/Documentation/Splunk/latest/AdvancedDev/ModInputsScripts.
        """
        
        # Note: there is no distinction between a None value and blank value,
        # as modular input UIs does not recognize such a distinction.
        if name is None or len(name.strip()) == 0:
            raise ValueError("The name parameter cannot be empty.")
        
        if title is None or len(title.strip()) == 0:
            raise ValueError("The title parameter cannot be empty.")
        
        if description is None or len(description.strip()) == 0:
            raise ValueError("The description parameter cannot be empty.")
        
        self.name = name
        self.title = title
        self.description = description
        self.required_on_create = required_on_create
        self.required_on_edit = required_on_edit
            
    def to_python(self, value):
        """
        Convert the field to a Python object. Should throw a FieldValidationException if the data is invalid.
        
        Arguments:
        value -- The value to convert
        """
        
        # No standard validation here; the modular input framework handles empty values.         
        return value

    def to_string(self, value):
        """
        Convert the field to a string value that can be returned. Should throw a FieldValidationException if the data is invalid.
        
        Arguments:
        value -- The value to convert
        """
        
        return str(value)


class DurationField(Field):
    """
    The duration field represents a duration as represented by a string such as 1d for a 24 hour period.
    
    The string is converted to an integer indicating the number of seconds.
    """
    
    DURATION_RE = re.compile("(?P<duration>[0-9]+)\s*(?P<units>[a-z]*)", re.IGNORECASE)
    
    MINUTE = 60
    HOUR = 3600
    DAY = 86400
    WEEK = 604800
    
    UNITS = {
             'w': WEEK,
             'week': WEEK,
             'd': DAY,
             'day': DAY,
             'h': HOUR,
             'hour': HOUR,
             'm': MINUTE,
             'min': MINUTE,
             'minute': MINUTE,
             's': 1
             }
    
    def to_python(self, value):
        Field.to_python(self, value)
        
        # Parse the duration
        m = DurationField.DURATION_RE.match(value)

        # Make sure the duration could be parsed
        if m is None:
            raise FieldValidationException("The value of '%s' for the '%s' parameter is not a valid duration" % (str(value), self.name))
        
        # Get the units and duration
        d = m.groupdict()
        
        units = d['units']
        
        # Parse the value provided
        try:
            duration = int(d['duration'])
        except ValueError:
            raise FieldValidationException("The duration '%s' for the '%s' parameter is not a valid number" % (d['duration'], self.name))
        
        # Make sure the units are valid
        if len(units) > 0 and units not in DurationField.UNITS:
            raise FieldValidationException("The unit '%s' for the '%s' parameter is not a valid unit of duration" % (units, self.name))
        
        # Convert the units to seconds
        if len(units) > 0:
            return duration * DurationField.UNITS[units]
        else:
            return duration

    def to_string(self, value):
        return str(value)


class BooleanField(Field):
    
    def to_python(self, value):
        Field.to_python(self, value)
        
        if value in [True, False]:
            return value

        elif str(value).strip().lower() in ["true", "t", "1"]:
            return True

        elif str(value).strip().lower() in ["false", "f", "0"]:
            return False
        
        raise FieldValidationException("The value of '%s' for the '%s' parameter is not a valid boolean" % (str(value), self.name))

    def to_string(self, value):

        if value == True:
            return "1"

        elif value == False:
            return "0"
        
        return str(value)
    
    def get_data_type(self):
        return Field.DATA_TYPE_BOOLEAN
    
    
class ListField(Field):
    
    def to_python(self, value):
        
        Field.to_python(self, value)
        
        if value is not None:
            return value.split(",")
        else:
            return []
    
    def to_string(self, value):

        if value is not None:
            return ",".join(value)
        
        return ""
    
    
class RegexField(Field):
    
    def to_python(self, value):
        
        Field.to_python(self, value)
        
        if value is not None:
            try:
                return re.compile(value)
            except Exception as e:
                raise FieldValidationException(str(e))
        else:
            return None
    
    def to_string(self, value):

        if value is not None:
            return value.pattern
        
        return ""


class IntegerField(Field):
    
    def to_python(self, value):
        
        Field.to_python(self, value)
        
        if value is not None:
            try:
                return int(value)
            except ValueError as e:
                raise FieldValidationException(str(e))
        else:
            return None
    
    def to_string(self, value):

        if value is not None:
            return str(value)
        
        return ""
    
    def get_data_type(self):
        return Field.DATA_TYPE_NUMBER
    
    
class FloatField(Field):
    
    def to_python(self, value):
        
        Field.to_python(self, value)
        
        if value is not None:
            try:
                return float(value)
            except ValueError as e:
                raise FieldValidationException(str(e))
        else:
            return None
    
    def to_string(self, value):

        if value is not None:
            return str(value)
        
        return ""
    
    def get_data_type(self):
        return Field.DATA_TYPE_NUMBER

    
class RangeField(Field):

    def __init__(self, name, title, description, low, high, required_on_create=True, required_on_edit=False):
        super(RangeField, self).__init__(name, title, description, required_on_create, required_on_edit)
        self.low = low
        self.high = high
    
    def to_python(self, value):
        
        Field.to_python(self, value)
        
        if value is not None:
            try:
                tmp = int(value)
                return tmp >= self.low and tmp <= self.high
            except ValueError as e:
                raise FieldValidationException(str(e))
        else:
            return None
    
    def to_string(self, value):

        if value is not None:
            return str(value)
        
        return ""
    
    def get_data_type(self):
        return Field.DATA_TYPE_NUMBER


class ModularInputConfig(object):
    
    def __init__(self, server_host, server_uri, session_key, checkpoint_dir, configuration):
        self.server_host = server_host
        self.server_uri = server_uri
        self.session_key = session_key
        self.checkpoint_dir = checkpoint_dir
        self.configuration = configuration
        
    def __str__(self):
        attrs = ['server_host', 'server_uri', 'session_key', 'checkpoint_dir', 'configuration']
        return str({attr: str(getattr(self, attr)) for attr in attrs})
    
    @staticmethod
    def get_text(node, default=None):
        """
        Get the value of the text in the first node under the given node.
        
        Arguments:
        node -- The node that should have a text node under it.
        default -- The default text that ought to be returned if no text node could be found (defaults to none).
        """
        
        if node and node.firstChild and node.firstChild.nodeType == node.firstChild.TEXT_NODE:
            return node.firstChild.data
        else:
            return default
    
    @staticmethod
    def get_config_from_xml(config_str_xml):
        """
        Get the config from the given XML and return a ModularInputConfig instance.
        
        Arguments:
        config_str_xml -- A string of XML that represents the configuration provided by Splunk.
        """        
        configuration = {}
        
        # Parse the document
        doc = xml.dom.minidom.parseString(config_str_xml)
        root = doc.documentElement
        
        # Get the server_host
        server_host_node = root.getElementsByTagName("server_host")[0] 
        server_host = ModularInputConfig.get_text(server_host_node)
        
        # Get the server_uri
        server_uri_node = root.getElementsByTagName("server_uri")[0] 
        server_uri = ModularInputConfig.get_text(server_uri_node)
        
        # Get the session_key
        session_key_node = root.getElementsByTagName("session_key")[0] 
        session_key = ModularInputConfig.get_text(session_key_node)
        
        # Get the checkpoint directory
        checkpoint_node = root.getElementsByTagName("checkpoint_dir")[0] 
        checkpoint_dir = ModularInputConfig.get_text(checkpoint_node)
        
        # Parse the config
        conf_node = root.getElementsByTagName("configuration")[0]
        
        if conf_node:
            
            for stanza in conf_node.getElementsByTagName("stanza"):
                config = {}
                
                if stanza:
                    stanza_name = stanza.getAttribute("name")
                    
                    if stanza_name:
                        config["name"] = stanza_name
    
                        params = stanza.getElementsByTagName("param")
                        
                        for param in params:
                            param_name = param.getAttribute("name")
                            
                            config[param_name] = ModularInputConfig.get_text(param)
                            
                    configuration[stanza_name] = config

        return ModularInputConfig(server_host, server_uri, session_key, checkpoint_dir, configuration)


class ModularInput(object):
    
    # These arguments cover the standard fields that are always supplied
    standard_args = [
                BooleanField("disabled", "Disabled", "Whether the modular input is disabled or not"),
                Field("host", "Host", "The host that is running the input"),
                Field("index", "Index", "The index that data should be sent to"),
                IntegerField("interval", "Interval", "The interval the script will be run on"),
                Field("name", "Stanza name", "The name of the stanza for this modular input"),
                Field("source", "Source", "The source for events created by this modular input"),
                Field("sourcetype", "Stanza name", "The name of the stanza for this modular input")
                ]

    def _is_valid_param(self, name, val):
        '''Raise an error if the parameter is None or empty.'''
        if val is None:
            raise ValueError("The {0} parameter cannot be none".format(name))

        if len(val.strip()) == 0:
            raise ValueError("The {0} parameter cannot be empty".format(name))
        
        return val
    
    def _create_formatter_textnode(self, xmldoc, nodename, value):
        '''Shortcut for creating a formatter textnode.
        
        Arguments:
        xmldoc - A Document object.
        nodename - A string name for the node.
        '''
        node = xmldoc.createElement(nodename)
        text = xmldoc.createTextNode(str(value))
        node.appendChild(text)
        
        return node
                
    def _create_document(self):
        '''Create the document for sending XML streaming events.'''

        doc = Document()
        
        # Create the <stream> base element
        stream = doc.createElement('stream')
        doc.appendChild(stream)

        return doc
    
    def _create_event(self, doc, params, stanza, unbroken=False, close=True):
        '''Create an event for XML streaming output.
        
        Arguments:
        doc - a Document object.
        params - a dictionary of attributes for the event.
        stanza_name - the stanza
        '''

        # Create the <event> base element
        event = doc.createElement('event')
        
        # Indicate if this event is to be unbroken (meaning a </done> tag will 
        # need to be added by a future event.
        if unbroken:
            event.setAttribute('unbroken', '1')
        
        # Indicate if this script is single-instance mode or not.
        if self.streaming_mode == 'true':
            event.setAttribute('stanza', stanza)

        # Define the possible elements
        valid_elements = ['host', 'index', 'source', 'sourcetype', 'time', 'data']
        
        # Append the valid child elements. Invalid elements will be dropped.
        for element in filter(lambda x: x in valid_elements, params.keys()):
            event.appendChild(self._create_formatter_textnode(doc, element, params[element]))
            
        if close:
            event.appendChild(doc.createElement('done'))
        
        return event
    
    def _print_event(self, doc, event):
        '''Adds an event to XML streaming output.'''

        # Get the stream from the document.
        stream = doc.firstChild
        
        # Append the event.
        stream.appendChild(event)

        # Return the content as a string WITHOUT the XML header; remove the
        # child object so the next event can be returned and reuse the same
        # Document object.
        output = doc.documentElement.toxml()
        
        stream.removeChild(event)
        
        return output
        
    def _add_events(self, doc, events):
        '''Adds a set of events to XML streaming output.'''

        # Get the stream from the document.
        stream = doc.firstChild
        
        # Add the <event> node.
        for event in events:
            stream.appendChild(event)

        # Return the content as a string WITHOUT the XML header.
        return doc.documentElement.toxml()
    
    def __init__(self, scheme_args, args=None):
        """
        Set up the modular input.
        
        Arguments:
        title -- The title of the modular input (e.g. "Database Connector")
        description -- A description of the input (e.g. "Get data from a database")
        args -- A list of Field instances for validating the arguments
        """
        
        # Set the scheme arguments.
        for arg in ['title', 'description', 'use_external_validation', 'streaming_mode', 'use_single_instance']:
            setattr(self, arg, self._is_valid_param(arg, scheme_args.get(arg)))
                
        if args is None:
            self.args = []
        else:
            self.args = args[:]
                    
    def addArg(self, arg):
        """
        Add a given argument to the list of arguments.
        
        Arguments:
        arg -- An instance of Field that represents an argument.
        """
        
        if self.args is None:
            self.args = []
            
        self.args.append(arg)
    
    def usage(self, out=sys.stdout):
        """
        Print a usage statement.
        
        Arguments:
        out -- The stream to write the message to (defaults to standard output)
        """
        
        out.write("usage: %s [--scheme|--validate-arguments]")
    
    def do_scheme(self, out=sys.stdout):
        """
        Get the scheme and write it out to standard output.
        
        Arguments:
        out -- The stream to write the message to (defaults to standard output)
        """
        
        logger.info("Modular input: scheme requested")
        out.write(self.get_scheme())
        
        return True
        
    def get_scheme(self):
        """
        Get the scheme of the inputs parameters and return as a string.
        """
        
        # Create the XML document
        doc = Document()
        
        # Create the <scheme> base element
        element_scheme = doc.createElement("scheme")
        doc.appendChild(element_scheme)
        
        # Create the title element
        element_title = doc.createElement("title")
        element_scheme.appendChild(element_title)
        
        element_title_text = doc.createTextNode(self.title)
        element_title.appendChild(element_title_text)
        
        # Create the description element
        element_desc = doc.createElement("description")
        element_scheme.appendChild(element_desc)
        
        element_desc_text = doc.createTextNode(self.description)
        element_desc.appendChild(element_desc_text)
        
        # Create the use_external_validation element
        element_external_validation = doc.createElement("use_external_validation")
        element_scheme.appendChild(element_external_validation)
        
        element_external_validation_text = doc.createTextNode(self.use_external_validation)
        element_external_validation.appendChild(element_external_validation_text)
        
        # Create the streaming_mode element
        element_streaming_mode = doc.createElement("streaming_mode")
        element_scheme.appendChild(element_streaming_mode)
        
        element_streaming_mode_text = doc.createTextNode(self.streaming_mode)
        element_streaming_mode.appendChild(element_streaming_mode_text)

        # Create the use_single_instance element
        element_use_single_instance = doc.createElement("use_single_instance")
        element_scheme.appendChild(element_use_single_instance)
        
        element_use_single_instance_text = doc.createTextNode(self.use_single_instance)
        element_use_single_instance.appendChild(element_use_single_instance_text)
        
        # Create the elements to stored args element
        element_endpoint = doc.createElement("endpoint")
        element_scheme.appendChild(element_endpoint)
        
        element_args = doc.createElement("args")
        element_endpoint.appendChild(element_args)
        
        # Create the argument elements
        self.add_xml_args(doc, element_args)
        
        # Return the content as a string
        return doc.toxml()
        
    def add_xml_args(self, doc, element_args):
        """
        Add the arguments to the XML scheme.
        
        Arguments:
        doc -- The XML document
        element_args -- The element that should be the parent of the arg elements that will be added.
        """
        
        for arg in self.args:
            element_arg = doc.createElement("arg")
            element_arg.setAttribute("name", arg.name)
            
            element_args.appendChild(element_arg)
            
            # Create the title element
            element_title = doc.createElement("title")
            element_arg.appendChild(element_title)
            
            element_title_text = doc.createTextNode(arg.title)
            element_title.appendChild(element_title_text)
            
            # Create the description element
            element_desc = doc.createElement("description")
            element_arg.appendChild(element_desc)
            
            element_desc_text = doc.createTextNode(arg.description)
            element_desc.appendChild(element_desc_text)
            
            # Create the data_type element
            element_data_type = doc.createElement("data_type")
            element_arg.appendChild(element_data_type)
            
            element_data_type_text = doc.createTextNode(arg.get_data_type())
            element_data_type.appendChild(element_data_type_text)

            # Create the required_on_create element
            element_required_on_create = doc.createElement("required_on_create")
            element_arg.appendChild(element_required_on_create)
            
            element_required_on_create_text = doc.createTextNode("true" if arg.required_on_create else "false")
            element_required_on_create.appendChild(element_required_on_create_text)

            # Create the required_on_save element
            element_required_on_edit = doc.createElement("required_on_edit")
            element_arg.appendChild(element_required_on_edit)
            
            element_required_on_edit_text = doc.createTextNode("true" if arg.required_on_edit else "false")
            element_required_on_edit.appendChild(element_required_on_edit_text)
        
    def do_validation(self, in_stream=sys.stdin):
        """
        Get the validation data from standard input and attempt to validate it. Returns true if the arguments validated, false otherwise.
        
        Arguments:
        in_stream -- The stream to get the input from (defaults to standard input)
        """
        
        data = self.get_validation_data()
        
        try:
            self.validate(data)
            return True
        except FieldValidationException as e:
            self.print_error(str(e))
            return False
            
    def validate(self, arguments):
        """
        Validate the argument dictionary where each key is a stanza.
        
        Arguments:
        arguments -- The arguments as an dictionary where the key is the stanza and the value is a dictionary of the values.
        """
        
        # Check each stanza
        for stanza, parameters in arguments.items():
            self.validate_parameters(stanza, parameters)
        return True
            
    def validate_parameters(self, parameters):
        """
        Validate the parameter set for a stanza and returns a dictionary of cleaner parameters.
        
        Arguments:
        parameters -- The list of parameters
        """
        
        cleaned_params = {}
        
        # Append the arguments list such that the standard fields that Splunk provides are included
        all_args = {}
        
        for a in self.standard_args:
            all_args[a.name] = a
        
        for a in self.args:
            all_args[a.name] = a
        
        # Convert and check the parameters
        for name, value in parameters.items():
            
            # If the argument was found, then validate and convert it
            if name in all_args:
                cleaned_params[name] = all_args[name].to_python(value)
                
            # Throw an exception if the argument could not be found
            else:
                raise FieldValidationException("The parameter '%s' is not a valid argument" % (name))
            
        return cleaned_params
            
    def print_error(self, error, out=sys.stdout):
        """
        Prints the given error message to standard output.
        
        Arguments:
        error -- The message to be printed
        out -- The stream to write the message to (defaults to standard output)
        """
        
        out.write("<error><message>%s</message></error>" % xml.sax.saxutils.escape(error))
    
    def read_config(self, in_stream=sys.stdin):
        """
        Read the config from standard input and return the configuration.
        
        in_stream -- The stream to get the input from (defaults to standard input)
        """
        
        config_str_xml = in_stream.read()
        
        return ModularInputConfig.get_config_from_xml(config_str_xml)            
    
    def run(self, stanza, cleaned_params):
        """
        Run the input using the arguments provided.
        
        Arguments:
        stanza -- The name of the stanza
        cleaned_params -- The arguments following validation and conversion to Python objects.
        """
        
        raise Exception("Run function was not implemented")
    
    @staticmethod
    def get_file_path(checkpoint_dir, stanza):
        """
        Get the path to the checkpoint file.
        
        Arguments:
        checkpoint_dir -- The directory where checkpoints ought to be saved
        stanza -- The stanza of the input being used
        """
        
        return os.path.join(checkpoint_dir, hashlib.sha1(stanza).hexdigest() + ".json")
        
    @classmethod
    def last_ran(cls, checkpoint_dir, stanza):
        """
        Determines the date that the input was last run (the input denoted by the stanza name).
        
        Arguments:
        checkpoint_dir -- The directory where checkpoints ought to be saved
        stanza -- The stanza of the input being used
        """
        
        fp = None
        
        try:
            fp = open(cls.get_file_path(checkpoint_dir, stanza))
            checkpoint_dict = json.load(fp)
                
            return checkpoint_dict['last_run']
    
        finally:
            if fp is not None:
                fp.close()
        
    @classmethod
    def needs_another_run(cls, checkpoint_dir, stanza, interval, cur_time=None):
        """
        Determines if the given input (denoted by the stanza name) ought to be executed.
        
        Arguments:
        checkpoint_dir -- The directory where checkpoints ought to be saved
        stanza -- The stanza of the input being used
        interval -- The frequency that the analysis ought to be performed
        cur_time -- The current time (will be automatically determined if not provided)
        """
        
        try:
            last_ran = cls.last_ran(checkpoint_dir, stanza)
            
            return cls.is_expired(last_ran, interval, cur_time)
            
        except IOError as e:
            # The file likely doesn't exist
            logger.exception("The checkpoint file likely doesn't exist")
            return True
        except ValueError as e:
            # The file could not be loaded
            logger.exception("The checkpoint file could not be loaded")
            return True
        except Exception as e:
            #Catch all that enforces an extra run
            logger.exception("Unexpected exception caught, enforcing extra run, exception info: " + str(e))
            return True
        # Default return value
        return True
    
    @classmethod
    def time_to_next_run(cls, checkpoint_dir, stanza, duration):
        """
        Returns the number of seconds as int until the next run of the input is expected.
        Note that a minimum of 1 second is enforced to avoid a python loop of death
        constricting the system in rare checkpoint dir failure scenarios.
        Snake pun entirely intentional (pythons constrict prey to death, like your cpu).
        
        Arguments:
        checkpoint_dir -- The directory where checkpoints ought to be saved
        stanza -- The stanza of the input being used
        duration -- The frequency that the analysis ought to be performed
        """
        
        try:
            last_ran = cls.last_ran(checkpoint_dir, stanza)
            last_target_time = last_ran + duration
            time_to_next = last_target_time - time.time()
            if time_to_next < 1:
                time_to_next = 1
            return time_to_next
        except IOError:
            # The file likely doesn't exist
            logger.warning("Could not read checkpoint file for last time run, likely does not exist, if this persists debug input immediately")
            return 1
        except ValueError:
            # The file could not be loaded
            logger.error("Could not read checkpoint file for last time run, if this persists debug input immediately")
            return 1
        except Exception as e:
            logger.exception("Unexpected exception caught, enforcing extra run, exception info: " + str(e))
            return 1
        # Default return value
        logger.info("This really should be impossible, but whatevs if your input is breaking check the duration calculations")
        return 1
    
    @classmethod
    def save_checkpoint(cls, checkpoint_dir, stanza, last_run):
        """
        Save the checkpoint state.
        
        Arguments:
        checkpoint_dir -- The directory where checkpoints ought to be saved
        stanza -- The stanza of the input being used
        last_run -- The time when the analysis was last performed
        """
        
        fp = None
        
        try:
            fp = open(cls.get_file_path(checkpoint_dir, stanza), 'w')
            
            d = {'last_run': last_run}
            
            json.dump(d, fp)
            
        except Exception:
            logger.exception("Failed to save checkpoint directory") 
            
        finally:
            if fp is not None:
                fp.close()
    
    @staticmethod
    def is_expired(last_run, interval, cur_time=None):
        """
        Indicates if the last run time is expired based .
        
        Arguments:
        last_run -- The time that the analysis was last done
        interval -- The interval that the analysis ought to be done (as an integer)
        cur_time -- The current time (will be automatically determined if not provided)
        """
        
        if cur_time is None:
            cur_time = time.time()
        
        if (last_run + interval) < cur_time:
            return True
        else:
            return False
    
    def do_run(self, in_stream=sys.stdin, log_exception_and_continue=False):
        """
        Read the config from standard input and return the configuration.
        
        in_stream -- The stream to get the input from (defaults to standard input)
        log_exception_and_continue -- If true, exceptions will not be thrown for invalid configurations and instead the stanza will be skipped.
        """
        
        # Run the modular import
        input_config = self.read_config(in_stream)
        
        # Alias checkpoint directory for readability.
        checkpoint_dir = input_config.checkpoint_dir
        
        # Is this input single instance mode?
        single_instance = str(getattr(self, "use_single_instance", '')).strip().lower() in ["true", "t", "1"]        
        
        # Validate all stanza parameters.
        stanzas = []
        for stanza_name, unclean_stanza in input_config.configuration.items():
            try:
                stanzas.append(self.validate_parameters(unclean_stanza))
            except FieldValidationException as e:
                if log_exception_and_continue:
                    # Discard the invalid stanza.
                    logger.error("Discarding invalid input stanza '%s': %s" % (stanza_name, str(e)))
                else:
                    raise e
            
        # Call the modular input's "run" method on valid stanzas, handling two cases:
        # a. If this script is in single_instance mode=true, we have received
        #    all stanzas in input_config.configuration. In this case,
        #    a duration parameter is not supported. The run() method may
        #    loop indefinitely, but we do not re-execute.
        # b. If this script is in single_instance_mode=false, each stanza
        #    can have a duration parameter (or not) specifying the time
        #    at which the individual stanza will be re-executed.
        #
        # Note: The "duration" parameter emulates the behavior of the "interval"
        # parameter available on Splunk 6.x and higher, and is mainly used by the
        # VMWare application.
        
        # TODO: A run() method may pass results back for optional processing
        results = None
        
        if stanzas:
            if single_instance:
                # Run the input across all defined stanzas and exit.
                results = self.run(stanzas, input_config)
            else:
                # Retrieve the single input stanza.
                stanza = stanzas[0]
                try:
                    duration = int(stanza.get('duration', -1))
                except ValueError as e:
                    # This should never happen unless the author of the modular input
                    # fails to specify "duration" as an IntegerField.
                    logger.error("Input stanza '%s' specified an invalid duration: %s" % (stanza.get('name', 'unknown'), str(e)))
                    # Exit with non-zero exit code so services/admin/inputstatus correctly reflects script status.
                    sys.exit(1)
    
                # Save the checkpoint(s).
                if duration > 0 and checkpoint_dir and ModularInput.needs_another_run(checkpoint_dir, stanza, duration):
                    while True:
                        # TODO: Checkpoints will build up in the config directory when
                        # the input stanza changes. This should probably be modified to
                        # use the name of the input itself, unhashed. Name collisions would
                        # be a configuration error.
                        self.save_checkpoint(checkpoint_dir, stanza, int(time.time()))
                        results = self.run(stanza, input_config)
                        # Results processing, if any, could occur here.
                        time.sleep(ModularInput.time_to_next_run(checkpoint_dir, stanza, duration))
                else:
                    # Run the single stanza and exit.
                    results = self.run(stanza, input_config)
        else:
            logger.info("No input stanzas defined")

        # Results processing, if any, could occur here.
    
    def get_validation_data(self, in_stream=sys.stdin):
        """
        Get the validation data from standard input
        
        Arguments:
        in_stream -- The stream to get the input from (defaults to standard input)
        """
        
        val_data = {}
    
        # Read everything from stdin
        val_str = in_stream.read()
    
        # Parse the validation XML
        doc = xml.dom.minidom.parseString(val_str)
        root = doc.documentElement
    
        item_node = root.getElementsByTagName("item")[0]
        if item_node:
    
            name = item_node.getAttribute("name")
            val_data["stanza"] = name
    
            params_node = item_node.getElementsByTagName("param")
            
            for param in params_node:
                name = param.getAttribute("name")
                
                if name and param.firstChild and param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                    val_data[name] = param.firstChild.data
    
        return val_data
    
    def validate_parameters_from_cli(self, argument_array=None):
        """
        Load the arguments from the given array (or from the command-line) and validate them.
        
        Arguments:
        argument_array -- An array of arguments (will get them from the command-line arguments if none)
        """
        
        # Get the arguments from the sys.argv if not provided
        if argument_array is None:
            argument_array = sys.argv[1:]
        
        # This is the list of parameters we will generate
        parameters = {}
        
        for i in range(0, len(self.args)):
            arg = self.args[i]
            
            if i < len(argument_array):
                parameters[arg.name] = argument_array[i]
            else:
                parameters[arg.name] = None
        
        # Now that we have simulated the parameters, go ahead and test them
        self.validate_parameters("unnamed", parameters)
    
    def execute(self, in_stream=sys.stdin, out_stream=sys.stdout):
        """
        Get the arguments that were provided from the command-line and execute the script.
        
        Arguments:
        in_stream -- The stream to get the input from (defaults to standard input)
        out_stream -- The stream to write the output to (defaults to standard output)
        """
        
        try:
            logger.info("Execute called")
            
            if len(sys.argv) > 1:
                if sys.argv[1] == "--scheme":
                    self.do_scheme(out_stream)
                    
                elif sys.argv[1] == "--validate-arguments":
                    logger.info("Modular input: validate arguments called")
                    
                    # Exit with a code of -1 if validation failed
                    if self.do_validation() == False:
                        sys.exit(-1)
                    
                else:
                    self.usage(out_stream)
            else:
                
                # Run the modular input
                self.do_run(in_stream, log_exception_and_continue=True)
                
            logger.info("Execution completed successfully")
            
        except Exception as e:
            
            logger.exception("Execution failed: %s" % (str(e)))
            
            # Make sure to grab any exceptions so that we can print a valid error message
            self.print_error(str(e), out_stream)