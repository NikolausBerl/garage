"""Base model classes."""
import abc
from collections import namedtuple
import warnings

import tensorflow as tf


class BaseModel(abc.ABC):
    """
    Interface-only abstract class for models.

    A Model contains the structure/configuration of a set of computation
    graphs, or can be understood as a set of networks. Using a model
    requires calling `build()` with given input placeholder, which can be
    either tf.placeholder, or the output from another model. This makes
    composition of complex models with simple models much easier.

    Examples:
        model = SimpleModel(output_dim=2)
        # To use a model, first create a placeholder.
        # In the case of TensorFlow, we create a tf.placeholder.
        input_ph = tf.placeholder(tf.float32, shape=(None, 2))

        # Building the model
        output = model.build(input_ph)

        # We can also pass the output of a model to another model.
        # Here we pass the output from the above SimpleModel object.
        model_2 = ComplexModel(output_dim=2)
        output_2 = model_2.build(output)

    """

    def build(self, *inputs):
        """
        Output of model with the given input placeholder(s).

        This function is implemented by subclasses to create their computation
        graphs, which will be managed by Model. Generally, subclasses should
        implement `build()` directly.

        Args:
            inputs: Tensor input(s) for the model.

        Return:
            output: Tensor output(s) of the model.
        """
        pass

    @property
    def name(self):
        """Name for this Model."""
        pass

    @property
    def parameters(self):
        """
        Parameters of the Model.

        The output of a model is determined by its parameter. It could be
        the weights of a neural network model or parameters of a loss
        function model.
        """
        pass

    @parameters.setter
    def parameters(self, parameters):
        """Set parameters of the Model."""
        pass


class Network:
    """
    Network class For TensorFlow.

    A Network contains connectivity information by inputs/outputs.
    When a Network is built, it appears as a subgraph in the computation
    graphs, scoped by the Network name. All Networks built with the same
    model share the same parameters, i.e same inputs yield to same outputs.

    Args:
      model: The model building this network.
      inputs: Input Tensor(s).
      name: Name of the network, which is also the name scope.
    """

    @property
    def input(self):
        """Tensor input of the Network."""
        return self._inputs[0]

    @property
    def inputs(self):
        """Tensor inputs of the Network."""
        return self._inputs

    @property
    def output(self):
        """Tensor output of the Network."""
        return self._outputs[0]

    @property
    def outputs(self):
        """Tensor outputs of the Network."""
        return self._outputs


class Model(BaseModel):
    r"""
    Model class for TensorFlow.

    A TfModel only contains the structure/configuration of the underlying
    computation graphs. Connectivity information are all in Network class.
    A TfModel contains zero or more Network.

    When a Network is created, it reuses the parameter from the
    model and can be accessed by calling model.networks['network_name'],
    If a Network is built without given a name, the name "default" will
    be used.

    ***
    Do not call tf.global_variable_initializers() after building a model as it
    will reassign random weights to the model.
    The parameters inside a model will be initialized when calling build().
    ***

    Pickling is handled automatcailly. The target weights should be assigned to
    self._default_parameters before pickling, so that the newly created model
    can check if target weights exist or not. When unpickled, the unserialized
    model will load the weights from self._default_parameters.

    The design is illustrated as the following:

         input_1                      input_2
            |                            |
    ============== Model (TfModel)===================
    |       |                            |          |
    |       |            Parameters      |          |
    |    =============  /           \  ============ |
    |    |  default  | /             \ | Network2 | |
    |    | (Network) |/               \|(Network) | |
    |    =============                 ============ |
    |       |                            |          |
    =================================================
            |                            |
            |                            |
    (model.networks['default'].outputs)  |
                        model.networks['Network2'].outputs


    Examples are also available in tests/garage/tf/models/test_model.

    Args:
      name (str): Name of the model. It will also become the variable scope
      of the model. Every model should have a unique name.
    """

    def __init__(self, name):
        super().__init__()
        self._name = name or type(self).__name__  # name default to class
        self._networks = {}
        self._default_parameters = None
        self._variable_scope = None

    def build(self, *inputs, name=None):
        """
        Build a Network with the given input(s).

        ***
        Do not call tf.global_variable_initializers() after building a model
        as it will reassign random weights to the model.
        The parameters inside a model will be initialized when calling build().
        ***

        It uses the same, fixed variable scope for all Networks, to ensure
        parameter sharing. Different Networks must have an unique name.

        Args:
          inputs: Tensor input(s), recommended to be positional arguments, e.g.
            def build(self, state_input, action_input, name=None).
          name(str): Name of the model, which is also the name scope of the
            model.

        Raises:
          ValueError when a Network with the same name is already built.

        Returns:
          outputs: Output tensor of the model with the given inputs.

        """
        network_name = name or 'default'

        if not self._networks:
            # First time building the model, so self._networks are empty
            # We store the variable_scope to reenter later when we reuse it
            with tf.variable_scope(
                    self._name, reuse=False) as self._variable_scope:
                with tf.name_scope(name=network_name):
                    network = Network()
                    network._inputs = inputs
                    network._outputs = self._build(*inputs)
                variables = self._get_variables().values()
                tf.get_default_session().run(
                    tf.variables_initializer(variables))
                if self._default_parameters:
                    self.parameters = self._default_parameters
        else:
            if network_name in self._networks:
                raise ValueError(
                    'Network {} already exists!'.format(network_name))
            with tf.variable_scope(
                    self._variable_scope, reuse=True,
                    auxiliary_name_scope=False):
                with tf.name_scope(name=network_name):
                    network = Network()
                    network._inputs = inputs
                    network._outputs = self._build(*inputs)
        spec = self.network_output_spec()
        if spec:
            c = namedtuple(network_name,
                           [*spec, 'input', 'output', 'inputs', 'outputs'])
            if isinstance(network.outputs, tuple):
                assert len(spec) == len(network.outputs), (
                    'network_output_spec must have same length as outputs!')
                self._networks[network_name] = c(
                    *network.outputs, network.input, network.output,
                    network.inputs, network.outputs)
            else:
                self._networks[network_name] = c(
                    network.outputs, network.input, network.output,
                    network.inputs, network.outputs)
        else:
            self._networks[network_name] = network
        return network.outputs

    def _build(self, *inputs):
        """
        Output of the model given input placeholder(s).

        User should implement _build() inside their subclassed model,
        and construct the computation graphs in this function.

        Args:
            inputs: Tensor input(s), recommended to be position arguments, e.g.
              def build(self, state_input=None, action_input=None, name=None).
              It would be usually same as the inputs in build().
        Return:
            output: Tensor output(s) of the model.
        """
        pass

    def network_output_spec(self):
        """
        Network output spec.

        Return:
            *inputs: List of key(str) for the network outputs.
        """
        return []

    @property
    def networks(self):
        """Networks of the model."""
        return self._networks

    @property
    def parameters(self):
        """Parameters of the model."""
        _variables = self._get_variables()
        if _variables:
            return tf.get_default_session().run(_variables)
        else:
            return _variables

    @parameters.setter
    def parameters(self, parameters):
        """Set model parameters."""
        variables = self._get_variables()
        for name, var in variables.items():
            if name in parameters:
                var.load(parameters[name])
            else:
                warnings.warn('No value provided for variable {}'.format(name))

    @property
    def name(self):
        """Name of the model."""
        return self._name

    def _get_variables(self):
        if self._variable_scope:
            return {v.name: v for v in self._variable_scope.global_variables()}
        else:
            return dict()

    def __getstate__(self):
        """Object.__getstate__."""
        new_dict = self.__dict__.copy()
        del new_dict['_networks']
        new_dict['_default_parameters'] = self.parameters
        return new_dict

    def __setstate__(self, state):
        """Object.__setstate__."""
        self.__dict__.update(state)
        self._networks = {}
