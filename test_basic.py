"""
Simple syntax validation and basic functionality test.
"""

import sys
import os

# Add the current directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported without syntax errors."""
    print("Testing module imports...")
    
    try:
        # Test core modules
        from core.parsing_models import ParsingConfig, SuccessLevel, ParsingResult
        print("✅ parsing_models imported successfully")
        
        from core.parsing_strategies import DirectJSONStrategy, MarkdownBlockStrategy
        print("✅ parsing_strategies imported successfully")
        
        from core.validation_engine import ValidationEngine
        print("✅ validation_engine imported successfully")
        
        from core.enhanced_response_parser import EnhancedResponseParser
        print("✅ enhanced_response_parser imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality without external dependencies."""
    print("\nTesting basic functionality...")
    
    try:
        from core.parsing_models import ParsingConfig, SuccessLevel
        from core.parsing_strategies import DirectJSONStrategy, ExtractionContext
        
        # Test configuration creation
        config = ParsingConfig()
        print("✅ ParsingConfig created")
        
        # Test strategy creation
        strategy = DirectJSONStrategy(config)
        print("✅ DirectJSONStrategy created")
        
        # Test extraction context
        context = ExtractionContext(
            original_response="test",
            response_length=4,
            detected_format="json",
            has_code_blocks=False,
            has_json_markers=True
        )
        print("✅ ExtractionContext created")
        
        # Test simple JSON extraction
        test_response = '{"test": "value", "number": 42}'
        success, content, error = strategy.extract_content(test_response, context)
        
        if success and content:
            print("✅ Basic JSON extraction works")
            return True
        else:
            print(f"❌ JSON extraction failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def test_enhanced_parser_basic():
    """Test enhanced parser basic creation."""
    print("\nTesting enhanced parser creation...")
    
    try:
        from core.enhanced_response_parser import EnhancedResponseParser
        from core.parsing_models import ParsingConfig
        
        config = ParsingConfig()
        parser = EnhancedResponseParser(config)
        
        print("✅ EnhancedResponseParser created successfully")
        
        # Test get statistics
        stats = parser.get_parsing_statistics()
        print(f"✅ Parser statistics: {len(stats)} configuration items")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced parser test failed: {e}")
        return False

def main():
    """Run all basic tests."""
    print("Enhanced Parser Basic Validation Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_basic_functionality,
        test_enhanced_parser_basic
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("✅ All basic tests PASSED! Enhanced parser syntax is correct.")
        return True
    else:
        print("❌ Some tests FAILED! Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)