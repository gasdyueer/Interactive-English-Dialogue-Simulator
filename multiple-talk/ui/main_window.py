# main_window.py

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QProgressBar, QLineEdit,
    QDialog, QFormLayout, QComboBox, QSpinBox, QMessageBox, QListWidgetItem,
    QSizePolicy, QSpacerItem, QPlainTextEdit, QDialogButtonBox, QTextEdit
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QIcon, QColor # Optional: for icons and styling

from core.conversation_manager import ConversationManager, State
from core.step import Step


class AddStepDialog(QDialog):
    """添加/编辑步骤的对话框"""
    def __init__(self, step_to_edit: Step | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加/编辑步骤" if step_to_edit else "添加步骤")

        self.layout = QVBoxLayout(self)
        self.formLayout = QFormLayout()

        self.step_type_combo = QComboBox()
        self.step_type_combo.addItems(["TTS", "ASR"])
        self.formLayout.addRow("步骤类型:", self.step_type_combo)

        self.tts_content_edit = QTextEdit() # 使用多行编辑
        self.tts_content_edit.setPlaceholderText("输入要转为语音的文本")
        self.tts_label = QLabel("TTS 文本内容:")
        self.formLayout.addRow(self.tts_label, self.tts_content_edit)

        self.asr_duration_spin = QSpinBox()
        self.asr_duration_spin.setRange(0, 300) # 0 到 300 秒
        self.asr_duration_spin.setSuffix(" 秒 (0表示手动停止)")
        self.asr_duration_spin.setToolTip("设置建议的录音时长，0表示需要手动点击停止录音按钮")
        self.asr_duration_label = QLabel("ASR 录音时长:")
        self.formLayout.addRow(self.asr_duration_label, self.asr_duration_spin)

        self.layout.addLayout(self.formLayout)

        # --- 按钮 ---
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)

        # --- 连接信号 ---
        self.step_type_combo.currentIndexChanged.connect(self.update_ui_for_step_type)

        # --- 初始化 ---
        if step_to_edit:
            self.step = step_to_edit
            self.step_type_combo.setCurrentText(step_to_edit.step_type)
            if step_to_edit.step_type == "TTS":
                self.tts_content_edit.setText(step_to_edit.content)
            elif step_to_edit.step_type == "ASR":
                self.asr_duration_spin.setValue(int(step_to_edit.duration) if step_to_edit.duration else 0)
        else:
            self.step = None # 表示新建

        self.update_ui_for_step_type() # 根据初始类型设置UI显隐

        self.setMinimumWidth(400) # 设置对话框最小宽度


    def update_ui_for_step_type(self):
        """根据选择的步骤类型，显示/隐藏相关控件"""
        step_type = self.step_type_combo.currentText()
        is_tts = (step_type == "TTS")
        self.tts_label.setVisible(is_tts)
        self.tts_content_edit.setVisible(is_tts)
        self.asr_duration_label.setVisible(not is_tts)
        self.asr_duration_spin.setVisible(not is_tts)

    def get_step_data(self) -> tuple[str, str, float | None] | None:
         """获取用户输入的数据"""
         step_type = self.step_type_combo.currentText()
         content = ""
         duration = None

         if step_type == "TTS":
             content = self.tts_content_edit.toPlainText().strip()
             if not content:
                 QMessageBox.warning(self, "输入错误", "TTS步骤必须包含文本内容。")
                 return None
         elif step_type == "ASR":
             duration_val = self.asr_duration_spin.value()
             duration = float(duration_val) if duration_val > 0 else None # 0表示None

         return step_type, content, duration


class MainWindow(QMainWindow):
    """主窗口应用程序"""
    def __init__(self, manager: ConversationManager):
        super().__init__()
        self.manager = manager
        self.setWindowTitle("多轮对话模拟器")
        self.setGeometry(100, 100, 800, 650) # x, y, width, height

        # --- 主布局 ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget) # 主布局改为水平

        # --- 左侧：流程控制和步骤列表 ---
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_panel.setFixedWidth(350) # 固定左侧宽度

        # 步骤管理区
        self.step_mgmt_layout = QHBoxLayout()
        self.add_step_btn = QPushButton("添加步骤")
        self.remove_step_btn = QPushButton("删除步骤")
        self.edit_step_btn = QPushButton("编辑步骤") # 新增编辑按钮
        self.step_mgmt_layout.addWidget(self.add_step_btn)
        self.step_mgmt_layout.addWidget(self.edit_step_btn)
        self.step_mgmt_layout.addWidget(self.remove_step_btn)
        self.left_layout.addLayout(self.step_mgmt_layout)


        # 步骤列表区
        self.step_list_widget = QListWidget()
        self.step_list_widget.setToolTip("对话步骤列表")
        self.left_layout.addWidget(self.step_list_widget)

         # 步骤移动按钮区
        self.step_move_layout = QHBoxLayout()
        self.move_up_btn = QPushButton("上移")
        self.move_down_btn = QPushButton("下移")
        self.step_move_layout.addWidget(self.move_up_btn)
        self.step_move_layout.addWidget(self.move_down_btn)
        self.left_layout.addLayout(self.step_move_layout)


        # 执行控制区
        self.exec_control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始")
        self.pause_btn = QPushButton("暂停")
        self.stop_btn = QPushButton("停止")
        self.exec_control_layout.addWidget(self.start_btn)
        self.exec_control_layout.addWidget(self.pause_btn)
        self.exec_control_layout.addWidget(self.stop_btn)
        self.left_layout.addLayout(self.exec_control_layout)

        self.main_layout.addWidget(self.left_panel)

        # --- 右侧：状态显示和交互区 ---
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)

        # 当前步骤显示区
        self.current_step_group = QWidget() # 使用QWidget做背景容器
        self.current_step_group.setObjectName("CurrentStepGroup") # For styling
        self.current_step_layout = QVBoxLayout(self.current_step_group)
        self.current_step_layout.setContentsMargins(10, 10, 10, 10) # 内边距
        self.current_step_label = QLabel("当前步骤: 无")
        self.current_step_label.setStyleSheet("font-weight: bold;")
        self.current_step_status_label = QLabel("状态: 空闲")
        self.step_progress_bar = QProgressBar()
        self.step_progress_bar.setVisible(False) # 默认隐藏 TTS 播放进度
        self.current_step_layout.addWidget(self.current_step_label)
        self.current_step_layout.addWidget(self.current_step_status_label)
        self.current_step_layout.addWidget(self.step_progress_bar)
        self.right_layout.addWidget(self.current_step_group)


        # 语音交互区
        self.voice_interaction_group = QWidget()
        self.voice_interaction_group.setObjectName("VoiceInteractionGroup")
        self.voice_interaction_layout = QVBoxLayout(self.voice_interaction_group)
        self.voice_interaction_layout.setContentsMargins(10, 10, 10, 10)

        self.interaction_title = QLabel("语音交互控制与结果")
        self.interaction_title.setStyleSheet("font-weight: bold;")
        self.voice_interaction_layout.addWidget(self.interaction_title)


        # TTS 播放控制 (简单显示状态，播放控制通过 Manager 触发)
        self.tts_status_label = QLabel("TTS 播放器: 停止")
        self.voice_interaction_layout.addWidget(self.tts_status_label)

        # ASR 录音控制
        self.asr_control_layout = QHBoxLayout()
        self.record_status_label = QLabel("录音状态: 未开始")
        self.start_record_btn = QPushButton("开始录音") # 虽然大部分是自动触发，但可能需要手动
        self.stop_record_btn = QPushButton("停止录音")
        self.start_record_btn.setEnabled(False) # 通常由流程触发，或手动模式？ 暂时禁用
        self.stop_record_btn.setEnabled(False)  # 只有在录音时才启用
        self.asr_control_layout.addWidget(self.record_status_label)
        self.asr_control_layout.addStretch()
        # self.asr_control_layout.addWidget(self.start_record_btn) # 隐藏手动开始按钮
        self.asr_control_layout.addWidget(self.stop_record_btn)
        self.voice_interaction_layout.addLayout(self.asr_control_layout)


        # ASR 识别结果显示
        self.asr_result_label = QLabel("ASR 识别结果:")
        self.asr_result_text = QTextEdit() # 用TextEdit显示结果，可以换行
        self.asr_result_text.setReadOnly(True)
        self.asr_result_text.setFixedHeight(60) # 限制初始高度
        self.asr_result_text.setPlaceholderText("等待识别结果...")
        self.voice_interaction_layout.addWidget(self.asr_result_label)
        self.voice_interaction_layout.addWidget(self.asr_result_text)

        self.right_layout.addWidget(self.voice_interaction_group)


        # 对话记录展示区
        self.history_group = QWidget()
        self.history_group.setObjectName("HistoryGroup")
        self.history_layout = QVBoxLayout(self.history_group)
        self.history_layout.setContentsMargins(10, 10, 10, 10)
        self.history_label = QLabel("完整对话记录:")
        self.history_label.setStyleSheet("font-weight: bold;")
        self.history_text_edit = QPlainTextEdit()
        self.history_text_edit.setReadOnly(True)
        self.history_text_edit.setPlaceholderText("对话流程执行后将在此显示完整记录...")
        self.history_layout.addWidget(self.history_label)
        self.history_layout.addWidget(self.history_text_edit)
        self.right_layout.addWidget(self.history_group)


        self.right_layout.addStretch() # 添加伸缩因子，让内容靠上
        self.main_layout.addWidget(self.right_panel)


        # --- 初始化UI状态 ---
        self.update_button_states(self.manager.get_state())
        self.update_step_list()

        # --- 连接信号和槽 ---
        self._connect_signals()


    def _connect_signals(self):
        """连接所有UI控件的信号到槽函数"""
        # 步骤管理按钮
        self.add_step_btn.clicked.connect(self.add_step)
        self.remove_step_btn.clicked.connect(self.remove_step)
        self.edit_step_btn.clicked.connect(self.edit_step)
        self.move_up_btn.clicked.connect(self.move_step_up)
        self.move_down_btn.clicked.connect(self.move_step_down)
        self.step_list_widget.itemSelectionChanged.connect(self.update_move_button_states)
        self.step_list_widget.itemDoubleClicked.connect(self.edit_step) # 双击编辑

        # 执行控制按钮
        self.start_btn.clicked.connect(self.manager.start_conversation)
        self.pause_btn.clicked.connect(self.manager.pause_conversation)
        self.stop_btn.clicked.connect(self.manager.stop_conversation)

        # ASR 录音按钮
        self.stop_record_btn.clicked.connect(self.manager.stop_asr_recording_manual)

        # Manager 信号 -> UI 更新槽函数
        self.manager.stateChanged.connect(self.update_button_states)
        self.manager.stepListChanged.connect(self.update_step_list)
        self.manager.stepExecutionStarting.connect(self.on_step_execution_starting)
        self.manager.stepExecutionFinished.connect(self.on_step_execution_finished)
        self.manager.stepStatusUpdated.connect(self.on_step_status_updated)
        self.manager.stepResultUpdated.connect(self.on_step_result_updated)
        self.manager.conversationFinished.connect(self.on_conversation_finished)
        self.manager.conversationStopped.connect(self.on_conversation_stopped_or_error) # 也用于错误
        self.manager.conversationStarted.connect(self.on_conversation_started)

        # TTS/ASR 交互信号 -> UI 更新
        self.manager.ttsPlaybackProgress.connect(self.update_tts_progress)
        self.manager.ttsPlaybackStateChanged.connect(self.update_tts_status)
        self.manager.asrRecordingStarted.connect(self.on_asr_recording_started)
        self.manager.asrRecordingStopped.connect(self.on_asr_recording_stopped)
        self.manager.asrRecordingFailed.connect(self.on_asr_recording_failed)
        self.manager.asrRecognitionResult.connect(self.update_asr_result) # 实时


    # --- 槽函数 (Manager 信号处理器) ---

    @Slot(State)
    def update_button_states(self, state: State):
        """根据Manager状态更新按钮的启用/禁用状态"""
        is_idle = (state == State.IDLE)
        is_running = state in [State.RUNNING, State.PLAYING_TTS, State.WAITING_FOR_TTS_SYNTHESIS, State.RECORDING_ASR, State.WAITING_FOR_ASR_RECOGNITION]
        is_paused = (state == State.PAUSED)
        is_finished = (state == State.FINISHED)
        is_stopped = (state == State.STOPPED)
        is_error = (state == State.ERROR)
        is_recording = (state == State.RECORDING_ASR)

        can_start = is_idle or is_finished or is_stopped or is_error or is_paused
        has_steps = self.step_list_widget.count() > 0

        self.start_btn.setEnabled(can_start and has_steps)
        self.start_btn.setText("开始" if (is_idle or is_finished or is_stopped or is_error) else "恢复")
        self.pause_btn.setEnabled(is_running)
        self.stop_btn.setEnabled(is_running or is_paused)

        # 步骤管理按钮在运行时禁用，防止修改流程
        can_manage_steps = is_idle or is_finished or is_stopped or is_error or is_paused # 允许暂停时修改
        self.add_step_btn.setEnabled(can_manage_steps)
        self.remove_step_btn.setEnabled(can_manage_steps and self.step_list_widget.currentRow() != -1)
        self.edit_step_btn.setEnabled(can_manage_steps and self.step_list_widget.currentRow() != -1)
        self.move_up_btn.setEnabled(can_manage_steps) # 具体在选中时再判断是否可移动
        self.move_down_btn.setEnabled(can_manage_steps)
        self.update_move_button_states() # 根据当前选中更新移动按钮

        # 录音按钮
        self.stop_record_btn.setEnabled(is_recording)

        # 更新状态栏标签
        self.current_step_status_label.setText(f"状态: {state.name}")
        if not is_running and not is_paused: # 清理当前步骤信息
              self.current_step_label.setText("当前步骤: 无")
              self.step_progress_bar.setVisible(False)
              self.step_progress_bar.setValue(0)

    @Slot()
    def update_step_list(self):
        """根据Manager中的步骤数据刷新UI列表"""
        current_row = self.step_list_widget.currentRow()  # 保存当前选中行
        self.step_list_widget.clear()
        steps = self.manager.get_steps()
        for i, step in enumerate(steps):
            # ... (logic to create item_text and item)
            item_text = f"{i + 1}. [{step.step_type}] "
            if step.step_type == "TTS":
                content_display = step.content if len(
                    step.content) < 50 else step.content[:47] + "..."
                item_text += f": {content_display}"
            elif step.step_type == "ASR":
                duration_text = f"(时长: {step.duration}s)" if step.duration else "(手动停止)"
                item_text += duration_text
                if step.result:
                    item_text += f" -> \"{step.result}\""  # 显示识别结果
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)  # 存储原始索引

            # 根据状态设置不同外观 (可选)
            if step.status == "进行中":
                item.setForeground(QColor("blue"))
            elif step.status == "已完成":
                item.setForeground(QColor("green"))
            elif step.status == "失败":
                item.setForeground(QColor("red"))
            # elif step.status == "待处理": item.setForeground(QColor("gray")) # Default color usually fine
            elif "暂停中" in step.status:
                item.setForeground(QColor("orange"))

            self.step_list_widget.addItem(item)

        # 恢复之前的选中行（如果有效）
        if 0 <= current_row < self.step_list_widget.count():
            self.step_list_widget.setCurrentRow(current_row)
        # else: # No need for explicit -1, default is no selection
        #    self.step_list_widget.setCurrentRow(-1)

        # self.update_move_button_states() # This is already called by update_button_states below

        # MODIFY HERE: Add this call to ensure button states are correct after list updates
        # Pass the current state from the manager
        self.update_button_states(self.manager.get_state())
        print(
            f"[UI] Step list updated. List count: {self.step_list_widget.count()}. Start button enabled: {self.start_btn.isEnabled()}")  # Debug print


    @Slot(int)
    def on_step_execution_starting(self, index: int):
        """当一个步骤开始执行时更新UI"""
        print(f"[UI] 步骤 {index} 开始执行")
        self.step_list_widget.setCurrentRow(index) # 高亮当前行
        step = self.manager.get_steps()[index]
        step_type_display = "TTS 文本" if step.step_type == "TTS" else "ASR 录音"
        content_display = f": {step.content[:60]}..." if step.step_type == "TTS" and step.content else ""
        duration_display = f"(时长: {step.duration}s)" if step.step_type == "ASR" and step.duration else "(手动)" if step.step_type == "ASR" else ""

        self.current_step_label.setText(f"当前步骤 {index+1}: [{step.step_type}] {content_display}{duration_display}")
        self.current_step_status_label.setText(f"状态: {step.status}") # Manager 已更新状态

        # 重置并可能显示进度条
        self.step_progress_bar.setValue(0)
        self.step_progress_bar.setVisible(step.step_type == "TTS") # 只为TTS显示播放进度
        # 清空上一 P 步的ASR结果
        if step.step_type == "TTS":
             self.asr_result_text.clear()


    @Slot(int, bool, str)
    def on_step_execution_finished(self, index: int, success: bool, result_or_error: str | None):
        """当一个步骤执行完成时更新UI"""
        print(f"[UI] 步骤 {index} 执行完成, 成功: {success}")
        self.update_step_list() # 刷新列表项状态颜色和ASR结果
        # 可能不需要特别做什么，因为列表刷新会处理
        # 如果是最后一步完成，on_conversation_finished 会处理
        # 如果失败，on_conversation_stopped_or_error 会处理


    @Slot(int, str)
    def on_step_status_updated(self, index: int, status_text: str):
         """更新特定步骤的状态显示"""
         # 更新当前步骤显示区的状态
         if index == self.manager.current_step_index and self.manager.get_state() not in [State.IDLE, State.FINISHED, State.STOPPED, State.ERROR]:
             self.current_step_status_label.setText(f"状态: {status_text}")
         # 更新列表项（通过刷新整个列表实现简单）
         self.update_step_list()

    @Slot(int, str)
    def on_step_result_updated(self, index: int, result_text: str):
         """更新特定步骤的ASR结果显示（用于列表）"""
         self.update_step_list() # 刷新列表以显示结果
         # 如果是当前步骤的最终结果，也更新结果区
         if index == self.manager.current_step_index:
              self.update_asr_result(index, result_text)


    @Slot(int)
    def update_tts_progress(self, percentage: int):
        """更新TTS播放进度条"""
        if self.step_progress_bar.isVisible():
            self.step_progress_bar.setValue(percentage)

    @Slot(bool)
    def update_tts_status(self, is_playing: bool):
        """更新TTS播放器状态标签"""
        if is_playing:
            self.tts_status_label.setText("TTS 播放器: 播放中...")
            self.step_progress_bar.setVisible(True)
        elif self.manager.get_state() == State.PAUSED:
             self.tts_status_label.setText("TTS 播放器: 已暂停")
             self.step_progress_bar.setVisible(True) # 暂停时也显示进度条
        else: # Stopped or finished
            self.tts_status_label.setText("TTS 播放器: 停止")
            self.step_progress_bar.setVisible(False)
            self.step_progress_bar.setValue(0)

    @Slot()
    def on_asr_recording_started(self):
        """ASR录音开始时更新UI"""
        self.record_status_label.setText("录音状态: 正在录音...")
        self.stop_record_btn.setEnabled(True)
        self.asr_result_text.setPlaceholderText("正在录音，请讲话...")
        self.asr_result_text.clear()


    @Slot(str)
    def on_asr_recording_stopped(self, filename: str):
        """ASR录音停止时更新UI"""
        self.record_status_label.setText(f"录音状态: 录音结束，等待识别...")
        self.stop_record_btn.setEnabled(False)
        self.asr_result_text.setPlaceholderText("录音结束，正在处理...")


    @Slot(str)
    def on_asr_recording_failed(self, error_msg: str):
        """ASR录音失败时更新UI"""
        self.record_status_label.setText(f"录音状态: 失败 ({error_msg})")
        self.stop_record_btn.setEnabled(False)
        QMessageBox.warning(self, "录音失败", error_msg)
        self.asr_result_text.setPlaceholderText("录音失败")


    @Slot(int, str)
    def update_asr_result(self, index:int, result_text: str):
        """更新ASR识别结果显示区域"""
         # 只更新当前活动步骤的结果显示
        if index == self.manager.current_step_index:
             self.asr_result_text.setText(result_text if result_text else "[识别无结果]")


    @Slot()
    def on_conversation_started(self):
         """对话开始时清空历史记录"""
         self.history_text_edit.clear()


    @Slot()
    def on_conversation_finished(self):
        """对话正常完成时"""
        self.current_step_label.setText("当前步骤: 无")
        self.current_step_status_label.setText("状态: 已完成")
        self.step_progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", "对话流程已成功执行完毕。")
        self.generate_conversation_history()

    @Slot()
    def on_conversation_stopped_or_error(self):
         """对话被停止或发生错误时"""
         final_state = self.manager.get_state()
         status_text = "状态: 已停止" if final_state == State.STOPPED else f"状态: 错误 ({final_state.name})"
         if self.manager.current_step_index != -1 and 0 <= self.manager.current_step_index < len(self.manager.steps):
              step = self.manager.steps[self.manager.current_step_index]
              self.current_step_label.setText(f"停止于步骤 {self.manager.current_step_index + 1}: [{step.step_type}]")
         else:
              self.current_step_label.setText("当前步骤: 无")

         self.current_step_status_label.setText(status_text)
         self.step_progress_bar.setVisible(False)
         self.stop_record_btn.setEnabled(False) # 确保录音停止按钮禁用
         self.tts_status_label.setText("TTS 播放器: 停止") # 确保播放器状态更新

         if final_state == State.ERROR:
              QMessageBox.warning(self, "错误", "对话流程因错误中断。请检查步骤或日志。")
         else: # Stopped
              QMessageBox.information(self, "停止", "对话流程已被用户停止。")

         self.generate_conversation_history() # 停止或错误时也显示当前记录


    def generate_conversation_history(self):
        """生成并显示完整的对话记录"""
        history = []
        for i, step in enumerate(self.manager.get_steps()):
             prefix = f"[{i+1}] "
             if step.step_type == "TTS":
                 history.append(f"{prefix}系统 (TTS): {step.content}")
             elif step.step_type == "ASR":
                 result_display = step.result if step.result else ("(未执行)" if step.status == "待处理" else "(无识别结果)")
                 history.append(f"{prefix}用户 (ASR): {result_display}")
                 if step.status == "失败":
                      history[-1] += " [失败]" # 标记失败
        self.history_text_edit.setPlainText("\n".join(history))


    # --- UI 动作槽函数 ---

    @Slot()
    def add_step(self):
        """弹出对话框添加新步骤"""
        dialog = AddStepDialog(parent=self)
        if dialog.exec():
            data = dialog.get_step_data()
            if data:
                step_type, content, duration = data
                self.manager.add_step(step_type, content, duration)
                # 添加后自动选中新加的行
                self.step_list_widget.setCurrentRow(self.step_list_widget.count() - 1)

    @Slot()
    def edit_step(self):
         """编辑选中的步骤"""
         current_row = self.step_list_widget.currentRow()
         if current_row == -1:
             QMessageBox.warning(self, "操作无效", "请先选择要编辑的步骤。")
             return

         original_index = self.step_list_widget.item(current_row).data(Qt.UserRole)
         step_to_edit = self.manager.get_steps()[original_index]

         dialog = AddStepDialog(step_to_edit=step_to_edit, parent=self)
         if dialog.exec():
             data = dialog.get_step_data()
             if data:
                 step_type, content, duration = data
                 # 更新 Step 对象属性
                 step_to_edit.step_type = step_type
                 step_to_edit.content = content
                 step_to_edit.duration = duration
                 step_to_edit.status = "待处理" # 编辑后重置状态
                 step_to_edit.result = None
                 step_to_edit.audio_file = None
                 print(f"[UI] 步骤 {original_index} 已编辑: {step_to_edit}")
                 # 刷新列表显示
                 self.manager.stepListChanged.emit() # 发送信号通知列表更新


    @Slot()
    def remove_step(self):
        """移除选中的步骤"""
        current_row = self.step_list_widget.currentRow()
        if current_row != -1:
            reply = QMessageBox.question(self, "确认删除",
                                         f"确定要删除步骤 {current_row + 1} 吗?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                original_index = self.step_list_widget.item(current_row).data(Qt.UserRole)
                self.manager.remove_step(original_index)
        else:
            QMessageBox.warning(self, "操作无效", "请先选择要删除的步骤。")

    @Slot()
    def move_step_up(self):
        """将选中步骤上移"""
        current_row = self.step_list_widget.currentRow()
        if current_row > 0:
            original_index = self.step_list_widget.item(current_row).data(Qt.UserRole)
            self.manager.move_step(original_index, original_index - 1)
            self.step_list_widget.setCurrentRow(current_row - 1) # 更新选中行

    @Slot()
    def move_step_down(self):
        """将选中步骤下移"""
        current_row = self.step_list_widget.currentRow()
        if current_row != -1 and current_row < self.step_list_widget.count() - 1:
            original_index = self.step_list_widget.item(current_row).data(Qt.UserRole)
            self.manager.move_step(original_index, original_index + 1)
            self.step_list_widget.setCurrentRow(current_row + 1) # 更新选中行

    @Slot()
    def update_move_button_states(self):
         """根据当前选中项更新移动按钮的可用状态"""
         current_row = self.step_list_widget.currentRow()
         count = self.step_list_widget.count()
         can_manage = self.add_step_btn.isEnabled() # 复用管理按钮的状态

         self.move_up_btn.setEnabled(can_manage and current_row > 0)
         self.move_down_btn.setEnabled(can_manage and current_row != -1 and current_row < count - 1)
         # 同时更新删除和编辑按钮的状态
         self.remove_step_btn.setEnabled(can_manage and current_row != -1)
         self.edit_step_btn.setEnabled(can_manage and current_row != -1)


    def closeEvent(self, event):
        """关闭窗口前确认"""
        # 可以添加保存状态等的逻辑
        # 停止可能在运行的流程
        if self.manager.get_state() not in [State.IDLE, State.FINISHED, State.STOPPED, State.ERROR]:
            self.manager.stop_conversation()
            # 短暂等待确保资源释放？
            QApplication.processEvents() # 处理一下事件循环

        # 清理临时文件？ (可选)
        # import shutil
        # if os.path.exists(TEMP_AUDIO_DIR):
        #     try:
        #         shutil.rmtree(TEMP_AUDIO_DIR)
        #         print("[UI] 临时音频文件夹已清理.")
        #     except Exception as e:
        #         print(f"[UI] 清理临时文件夹失败: {e}")

        event.accept()