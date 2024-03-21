
import logging
from motile_toolbox.visualization import to_napari_tracks_layer
from motile_toolbox.utils import relabel_segmentation
import time
import logging
from superqt.utils import thread_worker
from functools import partial
from typing import Optional, Any
from pathlib import Path

from napari.layers import Labels
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QLabel,
)
from qtpy.QtCore import QEvent, Signal

from .motile_solver import MotileSolver
from .solver_params import SolverParams
from .run import Run

logger = logging.getLogger(__name__)


class LoadButton(QPushButton):
    update_signal = Signal(SolverParams)
    def emit_update_signal(self, solver_params):
        print(f"Emitting parameter update signal with params {solver_params}")
        self.update_signal.emit(solver_params)

class BaseParamSpinBox():
    disable_signal = Signal()
    enable_signal = Signal(float)
    update_none_signal = Signal()
    def changeEvent(self, e):
        if e.type() == QEvent.EnabledChange:
            if self.isEnabled():
                self.enable_signal.emit(self.value())
            else:
                self.disable_signal.emit()
    
    def update_value(self, param_name, solver_params):
        value = solver_params.__getattribute__(param_name)
        if value is None:
            self.update_none_signal.emit()
            return
        print(f"Updating spinbox for {param_name} with value {value}")
        self.setValue(value)
    
    def connect_to_param(self, solver_params: SolverParams, param_name, load_btn):
        self.valueChanged.connect(
            partial(solver_params.__setattr__, param_name)
        )
        self.disable_signal.connect(
            partial(solver_params.__setattr__, param_name, None)
        )
        self.enable_signal.connect(
            partial(solver_params.__setattr__, param_name)
        )
        load_btn.update_signal.connect(
            partial(self.update_value, param_name)
        )

class EnableBox(QCheckBox):
    def connect_to_params_spinbox(self, param_spinbox: BaseParamSpinBox):
        self.stateChanged.connect(
                partial(self._on_toggle, param_spinbox)
            )
        param_spinbox.update_none_signal.connect(
            self._disable
        )

    def _on_toggle(self, widget: QWidget):
        if self.isChecked():
            widget.setEnabled(True)
        else:
            widget.setEnabled(False)

    def _disable(self):
        self.setChecked(False)

class EnableGroup(QGroupBox):
    def connect_to_params_spinbox(self, param_spinbox: BaseParamSpinBox):
        param_spinbox.update_none_signal.connect(
            self._disable
        )

    def _disable(self):
        self.setChecked(False)

class ParamSpinBox(QSpinBox, BaseParamSpinBox):
    pass

class ParamDoubleSpinBox(QDoubleSpinBox, BaseParamSpinBox):
    pass

class MotileWidget(QWidget):
    def __init__(self, viewer, graph_layer=False):
        super().__init__()
        self.viewer = viewer
        self.graph_layer = graph_layer
        self.solver_params = SolverParams()
        self.param_categories = {
            "data_params": ["max_edge_distance",  "max_children", "max_parents",],
            "constant_costs": ["appear_cost", "disappear_cost", "division_cost", "merge_cost",],
            "variable_costs": ["distance", "iou"],
        }
        self.base_path = Path(".")

        run_group = self._ui_run_motile()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._ui_select_labels_layer())
        main_layout.addWidget(self._ui_data_specific_hyperparameters())
        main_layout.addWidget(self._ui_constant_costs())
        for group in self._ui_variable_costs():
            main_layout.addWidget(group)
        main_layout.addWidget(run_group)
        self.setLayout(main_layout)

    def _ui_select_labels_layer(self) -> QGroupBox:
        # Select Labels layer
        layer_group = QGroupBox("Select Input Layer")
        layer_layout = QHBoxLayout()
        self.layer_selection_box = QComboBox()
        for layer in self.viewer.layers:
            if isinstance(layer, Labels):
                self.layer_selection_box.addItem(layer.name)
        if len(self.layer_selection_box) == 0:
            self.layer_selection_box.addItem("None")
        self.layer_selection_box.setToolTip("Select the labels layer you want to use for tracking")
        layer_layout.addWidget(self.layer_selection_box)
        layer_group.setLayout(layer_layout)
        return layer_group
    
    def get_labels_layer(self):
        curr_text = self.layer_selection_box.currentText()
        if curr_text == "None":
            return None
        return self.viewer.layers[curr_text]

    def _ui_data_specific_hyperparameters(self) -> QGroupBox:
        # Data-specific Hyperparameters section
        hyperparameters_group = QGroupBox("Data-Specific Hyperparameters")
        hyperparameters_layout = QFormLayout()
        for param_name in self.param_categories["data_params"]:
            field = self.solver_params.model_fields[param_name]
            spinbox = self._param_spinbox(param_name, negative=False)
            self._add_form_row(hyperparameters_layout, field.title, spinbox, tooltip=field.description)
        hyperparameters_group.setLayout(hyperparameters_layout)
        return hyperparameters_group
    
    def _ui_constant_costs(self) -> QGroupBox:
        # Constant Costs section
        constant_costs_group = QGroupBox("Constant Costs")
        constant_costs_layout = QVBoxLayout()
        for param_name in self.param_categories["constant_costs"]:
            layout = QHBoxLayout()
            field = self.solver_params.model_fields[param_name]
            spinbox = self._param_spinbox(param_name, negative=False)
            checkbox = EnableBox(field.title)
            checkbox.setToolTip(field.description)
            checkbox.setChecked(True)
            checkbox.connect_to_params_spinbox(spinbox)
            layout.addWidget(checkbox)
            layout.addWidget(spinbox)
            constant_costs_layout.addLayout(layout)

        constant_costs_group.setLayout(constant_costs_layout)
        return constant_costs_group
    
    def _ui_variable_costs(self) -> list[QGroupBox]:
        groups = []
        for param_type in self.param_categories["variable_costs"]:
            title = f"{param_type.title()} Cost"
            group_tooltip = f"Use the {param_type.title()} between objects as a linking feature."
            param_names = [f"{param_type}_weight", f"{param_type}_offset"]
            groups.append(self._create_feature_cost_group(
                title,
                param_names=param_names,
                checked=True,
                group_tooltip=group_tooltip,
            ))
        return groups

    def _create_feature_cost_group(
        self,
        title, 
        param_names,
        checked=True, 
        group_tooltip=None,
    ) -> EnableGroup:
        feature_cost = EnableGroup(title)
        feature_cost.setCheckable(True)
        feature_cost.setChecked(checked)
        feature_cost.setToolTip(group_tooltip)
        layout = QFormLayout()
        for param_name in param_names:
            field = self.solver_params.model_fields[param_name]
            spinbox = self._param_spinbox(param_name, negative=True)
            feature_cost.connect_to_params_spinbox(spinbox)
            self._add_form_row(layout, field.title, spinbox, tooltip=field.description)
        feature_cost.setLayout(layout)
        return feature_cost
    
    def _ui_run_motile(self) -> QGroupBox:
        # Specify name text box
        run_group = QGroupBox("Run")
        run_layout = QVBoxLayout()
        run_name_layout = QFormLayout()
        self.run_name = QLineEdit("tracks")
        run_name_layout.addRow("Run Name:", self.run_name)
        run_layout.addLayout(run_name_layout)

        print_params_btn = QPushButton("Print Params")
        print_params_btn.clicked.connect(self._print_parameters)
        run_layout.addWidget(print_params_btn)

        # Generate Tracks button
        generate_tracks_btn = QPushButton("Generate Tracks")
        generate_tracks_btn.clicked.connect(self._generate_tracks)
        generate_tracks_btn.setToolTip("Run tracking. Might take minutes for larger samples.")
        run_layout.addWidget(generate_tracks_btn)

        # Add running widget
        self.running_label = QLabel("Solver is running")
        self.running_label.hide()
        run_layout.addWidget(self.running_label)

        save_tracks_btn = QPushButton("Save Tracking Result")
        save_tracks_btn.clicked.connect(self._save_run)
        run_layout.addWidget(save_tracks_btn)


        self.load_tracks_selection = QComboBox()
        for run in self._list_runs():
            self.load_tracks_selection.addItem(run)
        if len(self.load_tracks_selection) == 0:
            self.load_tracks_selection.addItem("None")
        run_layout.addWidget(self.load_tracks_selection)
        self.load_tracks_btn = LoadButton("Load Tracking Result")
        self.load_tracks_btn.clicked.connect(
            partial(self._load_run, self.load_tracks_btn)
        )
        run_layout.addWidget(self.load_tracks_btn)

        run_group.setLayout(run_layout)
        return run_group
    
    def _save_run(self):
        run = Run(self.get_run_name(), self.solver_params)
        run.save(base_path=self.base_path)
    
    def _list_runs(self):
        return [dir.stem for dir in self.base_path.iterdir()]

    def _load_run(self, btn: LoadButton):
        run_dir = self.load_tracks_selection.currentText()
        if run_dir == "None":
            return
        run = Run.load(self.base_path / run_dir)
        self.set_run_name(run.run_name)
        print(f"Loaded parameters: {run.params}")
        self.solver_params = run.params
        btn.emit_update_signal(self.solver_params)

    def get_run_name(self):
        return self.run_name.text()
    
    def set_run_name(self, run_name):
        self.run_name.setText(run_name)

    

    def _print_parameters(self):
        print(f"Solving with parameters {self.solver_params}")

    def _generate_tracks(self):
        print(f"Solving with parameters {self.solver_params}")
        # Logic for generating tracks
        labels_layer = self.get_labels_layer()
        if labels_layer is None:
            return
        segmentation = labels_layer.data
        logger.debug(f"Segmentation shape: {segmentation.shape}")

        # do this in a separate thread so we can parse stdout and not block
        self.running_label.show()
        worker = self.solve_with_motile(segmentation, self.solver_params)
        worker.returned.connect(self._on_solve_complete)
        worker.start()
        

    @thread_worker
    def solve_with_motile(
        self, 
        segmentation,
        solver_params,
        ):
        if len(segmentation.shape) == 3:
            position_keys = ["y", "x"]
        elif len(segmentation.shape) == 4:
            position_keys = ["z", "y", "x"]
        solver = MotileSolver(solver_params)
        solution_nx_graph = solver.solve(segmentation, position_keys=position_keys)
        relabeled_segmentation = relabel_segmentation(solution_nx_graph, segmentation)
        tracks_layer_info = to_napari_tracks_layer(solution_nx_graph, location_keys=position_keys)
        
        return solution_nx_graph, relabeled_segmentation, tracks_layer_info, solver_params
    
    def _on_solve_complete(self, returned_worker):
        self.running_label.hide()
        solution_nx_graph, relabeled_segmentation, tracks_layer_info, solver_params = returned_worker  
        
        self.viewer.add_labels(relabeled_segmentation, name=self.get_run_name() + "_seg", metadata=solver_params.__dict__)
        # add tracks
        if solution_nx_graph.number_of_nodes() == 0:
            # TODO: Handle this edge case without error
            # warn("No tracks selected.")
            self.viewer.add_tracks([], name=self.get_run_name())
        track_data, track_props, track_edges = tracks_layer_info
        self.viewer.add_tracks(
            track_data, properties=track_props, graph=track_edges, 
            name=self.get_run_name(), metadata=solver_params.__dict__)

        logger.debug(self.graph_layer)
        if self.graph_layer:
            print("Adding graph layer")
            from ._graph_layer_utils import to_napari_graph_layer
            graph_layer = to_napari_graph_layer(solution_nx_graph, "Graph " + self.get_run_name(), loc_keys=("t", "y", "x"))
            self.viewer.add_layer(graph_layer)

    def _param_spinbox(self, param_name, negative=False) -> BaseParamSpinBox:
        """Create a double spinbox with one decimal place and link to solver param.

        Args:
            default_val (_type_): The default value to use in the spinbox
            negative (bool, optional): Whether to allow negative values in the spinbox.
                Defaults to False.

        Returns:
            BaseParamSpinbox: A spinbox linked to the solver param with the given name
        """
        
        field = self.solver_params.model_fields[param_name]
        # using subclass to allow Optional annotations. Might lead to strange behavior
        # if annotated with more than one (non-None) type
        if issubclass(int, field.annotation):
            spinbox = ParamSpinBox()
        elif issubclass(float, field.annotation):
            spinbox = ParamDoubleSpinBox()
            spinbox.setDecimals(1)
        else:
            raise ValueError(f"Expected dtype int or float, got {field.annotation}")
        max_val = 10000
        if negative:
            min_val = -1 * max_val
        else:
            min_val = 0
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(field.default)
        spinbox.connect_to_param(self.solver_params, param_name, self.load_tracks_btn)
        spinbox.changeEvent
        return spinbox

    def _add_form_row(self, layout: QFormLayout, label, value, tooltip=None):
        layout.addRow(label, value)
        row_widget = layout.itemAt(layout.rowCount() - 1, QFormLayout.LabelRole).widget()
        row_widget.setToolTip(tooltip)

