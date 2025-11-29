"""
Test script for final fixes - verifies all issues are resolved
"""
import sys
from main import AthenaApp
from handlers import CommandHandler


def test_command_handler_integration():
    """Test that CommandHandler is properly integrated"""
    print("="*60)
    print("TEST 1: CommandHandler Integration")
    print("="*60)
    
    app = AthenaApp()
    app.initialize_rag()
    
    # Verify query service exists
    assert app.query_service is not None, "Query service not initialized"
    print("✅ Query service initialized")
    
    # Verify CommandHandler can be created
    handler = CommandHandler(app.query_service, app.rag)
    print("✅ CommandHandler created")
    
    # Test some commands
    result = handler.handle_command("help")
    assert result.message is not None, "Help command should return message"
    assert "commands" in result.message.lower(), "Help should mention commands"
    print("✅ Help command works")
    
    result = handler.handle_command("stats")
    assert result.message is not None, "Stats command should return message"
    assert "chunks" in result.message.lower(), "Stats should show chunks"
    print("✅ Stats command works")
    
    print("\n✅ TEST 1 PASSED\n")


def test_query_service_availability():
    """Test that query service is always available"""
    print("="*60)
    print("TEST 2: Query Service Availability")
    print("="*60)
    
    app = AthenaApp()
    
    # Before RAG initialization
    assert app.query_service is None, "Query service should be None before init"
    print("✅ Query service None before init (expected)")
    
    # After RAG initialization
    app.initialize_rag()
    assert app.query_service is not None, "Query service should exist after init"
    print("✅ Query service initialized")
    
    # Verify it can execute queries
    result = app.query_service.execute_query("test question", n_results=1)
    assert result is not None, "Query should return result"
    print("✅ Query service can execute queries")
    
    print("\n✅ TEST 2 PASSED\n")


def test_llm_integration():
    """Test that LLM integration works"""
    print("="*60)
    print("TEST 3: LLM Integration")
    print("="*60)
    
    app = AthenaApp()
    
    # Check LLM availability
    has_local = app.ai.has_local_llm()
    has_cloud = app.ai.has_cloud_llm()
    
    print(f"   Local LLM: {'✅ Available' if has_local else '❌ Not available'}")
    print(f"   Cloud LLM: {'✅ Available' if has_cloud else '❌ Not available'}")
    
    assert has_local or has_cloud, "At least one LLM should be available"
    print("✅ At least one LLM is available")
    
    print("\n✅ TEST 3 PASSED\n")


def test_exceptions_module():
    """Test that exceptions module exists and works"""
    print("="*60)
    print("TEST 4: Exceptions Module")
    print("="*60)
    
    try:
        from exceptions import (
            AthenaError, ConfigError, RAGError, 
            LLMError, QueryError, DocumentProcessingError
        )
        print("✅ All exception classes imported")
        
        # Test that they're proper exceptions
        assert issubclass(ConfigError, AthenaError), "ConfigError should inherit from AthenaError"
        assert issubclass(LLMError, AthenaError), "LLMError should inherit from AthenaError"
        print("✅ Exception hierarchy correct")
        
        # Test raising
        try:
            raise QueryError("Test error")
        except AthenaError as e:
            assert str(e) == "Test error"
            print("✅ Exception raising/catching works")
        
        print("\n✅ TEST 4 PASSED\n")
        
    except ImportError:
        print("❌ TEST 4 FAILED: exceptions.py not found")
        print("   Create exceptions.py in project root")
        return False
    
    return True


def main():
    print("\n" + "="*60)
    print("ATHENA FINAL FIXES TEST SUITE")
    print("="*60 + "\n")
    
    try:
        test_command_handler_integration()
        test_query_service_availability()
        test_llm_integration()
        test_exceptions_module()
        
        print("="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nYour refactoring is complete! 🎉")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()