"""
Unit tests for Promise pattern (models/promise.py).

Tests Promise resolve/reject pattern, error handling, and data extraction.
"""

import pytest
from lindormmemobase.models.promise import Promise, PromiseUnpackError
from lindormmemobase.models.response import CODE, BaseResponse


@pytest.mark.unit
class TestPromise:
    """Test Promise class."""
    
    def test_resolve_creates_successful_promise(self):
        """Test that resolve() creates a successful promise."""
        promise = Promise.resolve("test_data")
        
        assert promise.ok() is True
        assert promise.data() == "test_data"
        assert promise.code() == CODE.SUCCESS
        assert promise.msg() == ""
    
    def test_resolve_with_dict_data(self):
        """Test resolving promise with dictionary data."""
        data = {"key": "value", "count": 42}
        promise = Promise.resolve(data)
        
        assert promise.ok() is True
        assert promise.data() == data
    
    def test_resolve_with_list_data(self):
        """Test resolving promise with list data."""
        data = [1, 2, 3, 4, 5]
        promise = Promise.resolve(data)
        
        assert promise.ok() is True
        assert promise.data() == data
    
    def test_resolve_with_none(self):
        """Test resolving promise with None value."""
        promise = Promise.resolve(None)
        
        assert promise.ok() is True
        assert promise.data() is None
    
    def test_reject_creates_failed_promise(self):
        """Test that reject() creates a failed promise."""
        promise = Promise.reject(CODE.BAD_REQUEST, "Invalid input")
        
        assert promise.ok() is False
        assert promise.code() == CODE.BAD_REQUEST
        assert "Invalid input" in promise.msg()
    
    def test_reject_with_internal_error(self):
        """Test rejecting with internal server error."""
        promise = Promise.reject(
            CODE.INTERNAL_SERVER_ERROR,
            "Something went wrong"
        )
        
        assert promise.ok() is False
        assert promise.code() == CODE.INTERNAL_SERVER_ERROR
        assert "Something went wrong" in promise.msg()
    
    def test_reject_without_message_fails(self):
        """Test that reject requires error message."""
        with pytest.raises(AssertionError):
            Promise.reject(CODE.BAD_REQUEST, None)
    
    def test_data_extraction_from_successful_promise(self):
        """Test extracting data from successful promise."""
        data = {"result": "success"}
        promise = Promise.resolve(data)
        
        extracted = promise.data()
        assert extracted == data
    
    def test_data_extraction_from_failed_promise_raises(self):
        """Test that extracting data from failed promise raises error."""
        promise = Promise.reject(CODE.BAD_REQUEST, "Error occurred")
        
        with pytest.raises(PromiseUnpackError) as exc_info:
            promise.data()
        
        assert "Error occurred" in str(exc_info.value)
    
    def test_error_message_format(self):
        """Test error message format."""
        promise = Promise.reject(CODE.SERVICE_UNAVAILABLE, "Service down")
        
        msg = promise.msg()
        assert "CODE 503" in msg
        assert "ERROR Service down" in msg
    
    def test_successful_promise_has_empty_message(self):
        """Test that successful promise has empty error message."""
        promise = Promise.resolve("data")
        
        assert promise.msg() == ""
    
    def test_to_response_conversion(self):
        """Test converting promise to response model."""
        data = {"key": "value"}
        promise = Promise.resolve(data)
        
        response = promise.to_response(BaseResponse)
        
        assert isinstance(response, BaseResponse)
        assert response.errno == CODE.SUCCESS
        assert response.errmsg == ""
        assert response.data == data
    
    def test_failed_promise_to_response(self):
        """Test converting failed promise to response."""
        promise = Promise.reject(CODE.BAD_REQUEST, "Invalid data")
        
        response = promise.to_response(BaseResponse)
        
        assert isinstance(response, BaseResponse)
        assert response.errno == CODE.BAD_REQUEST
        assert response.errmsg == "Invalid data"
        assert response.data is None
    
    def test_promise_code_method(self):
        """Test promise code() method."""
        success_promise = Promise.resolve("data")
        error_promise = Promise.reject(CODE.UNPROCESSABLE_ENTITY, "Error")
        
        assert success_promise.code() == CODE.SUCCESS
        assert error_promise.code() == CODE.UNPROCESSABLE_ENTITY
    
    def test_promise_with_complex_data(self):
        """Test promise with complex nested data."""
        complex_data = {
            "profiles": [
                {"id": "1", "name": "Profile 1"},
                {"id": "2", "name": "Profile 2"}
            ],
            "metadata": {
                "count": 2,
                "timestamp": "2024-12-01"
            }
        }
        promise = Promise.resolve(complex_data)
        
        assert promise.ok() is True
        assert promise.data() == complex_data


@pytest.mark.unit
class TestPromiseHelpers:
    """Test Promise helper methods from conftest."""
    
    def test_assert_promise_ok_helper(self, assert_ok):
        """Test assert_promise_ok helper function."""
        promise = Promise.resolve("data")
        
        # Should not raise
        assert_ok(promise)
    
    def test_assert_promise_ok_fails_on_error(self, assert_ok):
        """Test that assert_ok fails on error promise."""
        promise = Promise.reject(CODE.BAD_REQUEST, "Error")
        
        with pytest.raises(AssertionError):
            assert_ok(promise)
    
    def test_assert_promise_error_helper(self, assert_error):
        """Test assert_promise_error helper function."""
        promise = Promise.reject(CODE.BAD_REQUEST, "Error")
        
        # Should not raise
        assert_error(promise)
    
    def test_assert_promise_error_fails_on_success(self, assert_error):
        """Test that assert_error fails on successful promise."""
        promise = Promise.resolve("data")
        
        with pytest.raises(AssertionError):
            assert_error(promise)


@pytest.mark.unit
class TestCODEEnum:
    """Test CODE enum values."""
    
    def test_code_values_exist(self):
        """Test that all expected CODE values exist."""
        assert CODE.SUCCESS == 0
        assert CODE.BAD_REQUEST == 400
        assert CODE.INTERNAL_SERVER_ERROR == 500
        assert CODE.SERVICE_UNAVAILABLE == 503
        assert CODE.UNPROCESSABLE_ENTITY == 422
        assert CODE.SERVER_PARSE_ERROR == 1001
        assert CODE.SERVER_PROCESS_ERROR == 1002
        assert CODE.LLM_ERROR == 1003
        assert CODE.NOT_IMPLEMENTED == 1004
    
    def test_code_comparison(self):
        """Test CODE enum comparison."""
        assert CODE.SUCCESS != CODE.BAD_REQUEST
        assert CODE.INTERNAL_SERVER_ERROR == 500
