"""
Unit tests for text utilities (utils/text_utils.py).

Tests text processing functions like attribute unification and code block removal.
"""

import pytest
from lindormmemobase.utils.text_utils import attribute_unify, remove_code_blocks


@pytest.mark.unit
class TestAttributeUnify:
    """Test attribute_unify function."""
    
    def test_lowercase_conversion(self):
        """Test that attribute names are converted to lowercase."""
        assert attribute_unify("UPPERCASE") == "uppercase"
        assert attribute_unify("MixedCase") == "mixedcase"
        assert attribute_unify("lower") == "lower"
    
    def test_space_to_underscore(self):
        """Test that spaces are replaced with underscores."""
        assert attribute_unify("hello world") == "hello_world"
        assert attribute_unify("multiple spaces here") == "multiple_spaces_here"
        assert attribute_unify("single") == "single"
    
    def test_strip_whitespace(self):
        """Test that leading/trailing whitespace is removed."""
        assert attribute_unify("  spaces  ") == "spaces"
        assert attribute_unify("\ttabs\t") == "tabs"
        assert attribute_unify("  mixed  spaces  ") == "mixed__spaces"
    
    def test_combined_transformations(self):
        """Test multiple transformations together."""
        assert attribute_unify("  Hello World  ") == "hello_world"
        assert attribute_unify("UPPER CASE TEXT") == "upper_case_text"
        assert attribute_unify("  Mixed Case  Spaces  ") == "mixed_case__spaces"
    
    def test_empty_string(self):
        """Test empty string handling."""
        assert attribute_unify("") == ""
        assert attribute_unify("   ") == ""
    
    def test_special_characters(self):
        """Test handling of special characters."""
        assert attribute_unify("hello-world") == "hello-world"
        assert attribute_unify("hello_world") == "hello_world"
        assert attribute_unify("hello.world") == "hello.world"
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        assert attribute_unify("你好 世界") == "你好_世界"
        assert attribute_unify("Привет Мир") == "привет_мир"


@pytest.mark.unit
class TestRemoveCodeBlocks:
    """Test remove_code_blocks function."""
    
    def test_remove_simple_code_block(self):
        """Test removing simple code block markers."""
        input_text = """```
print("hello")
```"""
        expected = 'print("hello")'
        assert remove_code_blocks(input_text) == expected
    
    def test_remove_code_block_with_language(self):
        """Test removing code block with language specifier."""
        input_text = """```python
def hello():
    return "world"
```"""
        expected = """def hello():
    return "world\""""
        assert remove_code_blocks(input_text) == expected
    
    def test_remove_code_block_javascript(self):
        """Test removing JavaScript code block."""
        input_text = """```javascript
console.log('hello');
```"""
        expected = "console.log('hello');"
        assert remove_code_blocks(input_text) == expected
    
    def test_no_code_block_markers(self):
        """Test that content without markers is returned as-is."""
        input_text = "Just plain text"
        assert remove_code_blocks(input_text) == "Just plain text"
    
    def test_multiline_code_block(self):
        """Test removing markers from multiline code."""
        input_text = """```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```"""
        expected = """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)"""
        assert remove_code_blocks(input_text) == expected
    
    def test_remove_think_tags(self):
        """Test that <think> tags are removed."""
        input_text = """```
<think>This is thinking</think>
actual code here
```"""
        expected = "actual code here"
        assert remove_code_blocks(input_text) == expected
    
    def test_remove_think_tags_no_code_block(self):
        """Test removing think tags without code block."""
        input_text = "<think>thinking process</think>actual content"
        expected = "actual content"
        assert remove_code_blocks(input_text) == expected
    
    def test_nested_think_tags(self):
        """Test removing nested think tags."""
        input_text = """```
<think>outer<think>inner</think>outer</think>
code
```"""
        # Should remove outermost think tag
        assert "code" in remove_code_blocks(input_text)
        assert "<think>" not in remove_code_blocks(input_text)
    
    def test_whitespace_handling(self):
        """Test proper whitespace handling."""
        input_text = """  ```python
code here
```  """
        expected = "code here"
        assert remove_code_blocks(input_text) == expected
    
    def test_empty_code_block(self):
        """Test empty code block."""
        input_text = """```

```"""
        assert remove_code_blocks(input_text) == ""
    
    def test_code_block_with_numeric_language(self):
        """Test code block with numbers in language tag."""
        input_text = """```c99
int main() { return 0; }
```"""
        expected = "int main() { return 0; }"
        assert remove_code_blocks(input_text) == expected
    
    def test_preserves_internal_backticks(self):
        """Test that internal backticks are preserved."""
        input_text = """```
use `backticks` in code
```"""
        expected = "use `backticks` in code"
        assert remove_code_blocks(input_text) == expected
    
    def test_json_code_block(self):
        """Test JSON code block."""
        input_text = """```json
{
  "key": "value"
}
```"""
        expected = """{
  "key": "value"
}"""
        assert remove_code_blocks(input_text) == expected
    
    def test_partial_markers(self):
        """Test that partial markers don't trigger removal."""
        input_text = "```python\ncode without closing"
        # Should return as-is since pattern doesn't match
        assert remove_code_blocks(input_text) == input_text.strip()
    
    def test_multiple_think_tags(self):
        """Test multiple think tags."""
        input_text = """```
<think>first</think>
code
<think>second</think>
more code
```"""
        result = remove_code_blocks(input_text)
        assert "<think>" not in result
        assert "code" in result
        assert "more code" in result
