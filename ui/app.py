"""
Main application class for the RAG grading platform.
Coordinates all components and manages the overall application flow.
"""
import streamlit as st
from ui.state_manager import StateManager
from services.file_service import FileService
from services.grading_service import GradingService
from models.llm_manager import LLMManager
from ui.components.sidebar import SidebarComponent
from ui.components.grading_section import GradingSectionComponent
from ui.components.results_section import ResultsSectionComponent


class GradingApp:
    """Main application class that orchestrates the RAG grading platform."""
    
    def __init__(self):
        """Initialize the application with all required components."""
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all application components."""
        # Core managers
        self.state_manager = StateManager()
        self.llm_manager = self._get_cached_llm_manager()
        
        # Services
        self.file_service = FileService(self.state_manager)
        self.grading_service = GradingService(self.state_manager, self.llm_manager)
        
        # UI Components
        self.sidebar_component = SidebarComponent(
            self.state_manager, self.file_service, self.llm_manager
        )
        self.grading_section_component = GradingSectionComponent(
            self.state_manager, self.grading_service
        )
        self.results_section_component = ResultsSectionComponent(
            self.state_manager, self.grading_service
        )
    
    @st.cache_resource
    def _get_cached_llm_manager(_self):
        """Get a cached instance of LLM manager to avoid reinitialization."""
        try:
            return LLMManager()
        except Exception as e:
            st.error(f"LLM Manager 초기화 실패: {e}")
            return None
    
    def run(self):
        """Run the main application."""
        self._render_header()
        
        # Render sidebar
        self.sidebar_component.render()
        
        # Render main content
        self._render_main_content()
    
    def _render_header(self):
        """Render the application header."""
        st.title("RAG 기반 지리과 서답형 자동채점 플랫폼")
    
    def _render_main_content(self):
        """Render the main content area."""
        # Render grading section
        self.grading_section_component.render()
        
        # Get current question type from session state
        question_type = self._get_current_question_type()
        
        # Render results section if there are results
        if self.grading_service.has_grading_results():
            self.results_section_component.render(question_type)
    
    def _get_current_question_type(self) -> str:
        """
        Get the current question type from the UI state.
        
        Returns:
            str: Current question type, defaults to "서술형"
        """
        # This is a simplified approach - in a more complex app, 
        # you might want to store this in state_manager
        return "서술형"  # Default value
    
    def get_app_state(self) -> dict:
        """
        Get current application state for debugging.
        
        Returns:
            dict: Complete application state
        """
        return {
            "state_manager": self.state_manager.get_state_summary(),
            "sidebar": self.sidebar_component.get_sidebar_state(),
            "grading_section": self.grading_section_component.get_grading_section_state(),
            "results_section": self.results_section_component.get_results_section_state()
        }
    
    def reset_application(self):
        """Reset the application to initial state."""
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        # Reinitialize components
        self._initialize_components()
        
        st.success("애플리케이션이 초기화되었습니다.")
        st.rerun()


# Global app instance for debugging
_app_instance = None

def get_app_instance() -> GradingApp:
    """Get the global app instance for debugging purposes."""
    global _app_instance
    return _app_instance

def set_app_instance(app: GradingApp):
    """Set the global app instance."""
    global _app_instance
    _app_instance = app