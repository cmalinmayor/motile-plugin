from functools import partial
from types import NoneType

from motile_plugin.backend.solver_params import (
    CompoundSolverParam,
    SolverParams,
)
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .param_values import CompoundParamValue, EditableParamValue


class EditableParam(QWidget):
    def __init__(
        self,
        param_name: str,
        solver_params: SolverParams,
        negative: bool = False,
    ):
        """A widget for editing a parameter. Can be updated from
        the backend by calling update_from_params with a new SolverParams
        object. If changed in the UI, will emit a send_value signal which can
        be used to keep a SolverParams object in sync.

        Args:
            param_name (str): The name of the parameter to view in this UI row.
                Must correspond to one of the attributes of SolverParams.
            solver_params (SolverParams): The SolverParams object to use to
                initialize the view. Provides the title to display and the
                initial value.
            negative (bool, optional): Whether to allow negative values for
                this parameter. Defaults to False.
        """
        super().__init__()
        self.param_name = param_name
        field = solver_params.model_fields[param_name]
        self.dtype = field.annotation
        self.title = field.title
        self.negative = negative
        self.param_label = self._param_label_widget()
        self.param_label.setToolTip(field.description)
        self.param_value: CompoundParamValue | EditableParamValue
        if issubclass(CompoundSolverParam, self.dtype):
            self.param_value = CompoundParamValue(
                EditableParamValue(float, self.negative),
                EditableParamValue(float, self.negative),
            )
        else:
            self.param_value = EditableParamValue(float, self.negative)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.param_label)
        layout.addWidget(self.param_value)
        self.setLayout(layout)

        self.update_from_params(solver_params)

    def _param_label_widget(self) -> QLabel:
        return QLabel(self.title)

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            raise ValueError("Got None for required field {self.param_name}")
        else:
            self.param_value.update_value(param_val)


class OptionalEditableParam(EditableParam):
    def __init__(
        self,
        param_name: str,
        solver_params: SolverParams,
        negative: bool = False,
    ):
        """A widget for holding optional editable parameters. Adds a checkbox
        to the label, which toggles None-ness of the value.

        Args:
            param_name (str): _description_
            solver_params (SolverParams): _description_
            negative (bool, optional): _description_. Defaults to False.
        """
        super().__init__(param_name, solver_params, negative)
        self.param_label.toggled.connect(self.toggle_enable)

    def _param_label_widget(self) -> QCheckBox:
        return QCheckBox(self.title)

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            self.param_label.setChecked(False)
            self.param_value.setEnabled(False)
        else:
            self.param_label.setChecked(True)
            self.param_value.setEnabled(True)
            self.param_value.update_value(param_val)

    def toggle_enable(self, checked: bool):
        self.param_value.setEnabled(checked)
        value = self.param_value.get_value() if checked else None
        # force the parameter to say that the value has changed when we toggle
        self.param_value.valueChanged.emit(value)


class SolverParamsEditor(QWidget):
    """Widget for editing SolverParams.
    Spinboxes will be created for each parameter in SolverParams and linked such that
    editing the value in the spinbox will change the corresponding parameter.
    Checkboxes will also  be created for each optional parameter (group) and linked such
    that unchecking the box will update the parameter value to None, and checking will
    update the parameter to the current spinbox value.
    To update for a backend change to SolverParams, emit the new_params signal,
    which the spinboxes and checkboxes will connect to and use to update the
    UI and thus the stored solver params.
    """

    new_params = Signal(SolverParams)

    def __init__(self):
        super().__init__()
        self.solver_params = SolverParams()
        self.param_categories = {
            "hyperparams": ["max_edge_distance", "max_children"],
            "costs": [
                "appear_cost",
                "division_cost",
                "disappear_cost",
                "distance",
                "iou",
            ],
        }

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        debug_button = QPushButton("Print params")
        debug_button.clicked.connect(lambda: print(self.solver_params))
        main_layout.addWidget(debug_button)
        main_layout.addWidget(
            self._params_group(
                "Hyperparameters", "hyperparams", negative=False
            )
        )
        main_layout.addWidget(
            self._params_group("Costs", "costs", negative=True)
        )
        # for group in self._ui_variable_costs():
        # main_layout.addWidget(group)
        self.setLayout(main_layout)

    def _params_group(
        self, title: str, param_category: str, negative: bool
    ) -> QWidget:
        widget = QGroupBox(title)
        layout = QVBoxLayout()
        # layout.setContentsMargins(0, 0, 0, 0)
        # layout.addWidget(QLabel(title))
        for param_name in self.param_categories[param_category]:
            field = self.solver_params.model_fields[param_name]
            param_cls = (
                OptionalEditableParam
                if issubclass(NoneType, field.annotation)
                else EditableParam
            )
            param_row = param_cls(
                param_name, self.solver_params, negative=negative
            )
            param_row.param_value.valueChanged.connect(
                partial(self.solver_params.__setattr__, param_name)
            )
            self.new_params.connect(param_row.update_from_params)
            layout.addWidget(param_row)
        widget.setLayout(layout)
        return widget
