"""Document Analytics Library

This module provides core functionality for analyzing Markdown documents,
extracting topics, and calculating metrics like line, word, and character counts.
"""

from typing import Dict, List, Tuple, Optional
from markdown_it import MarkdownIt


class DocumentAnalyticsException(Exception):
    """Base exception for document analytics errors."""
    pass


def extract_topics(content: str) -> Dict[str, str]:
    """
    Extract topics and their content from a Markdown document.
    
    Args:
        content: Markdown content as string
        
    Returns:
        Dictionary mapping topic names to their content
    """
    if not content or not isinstance(content, str):
        raise DocumentAnalyticsException("Invalid document content")
    
    md = MarkdownIt()
    tokens = md.parse(content)
    
    # Find all h1 headings and their positions
    h1_positions = []
    for i, token in enumerate(tokens):
        if token.type == 'heading_open' and token.tag == 'h1':
            # The heading content is in the next token
            if i + 1 < len(tokens) and tokens[i + 1].type == 'inline':
                header_text = tokens[i + 1].content.strip()
                # Get the position of this heading in original text
                start_line = token.map[0] if token.map else -1
                h1_positions.append((start_line, header_text))
    
    # Split content by line for easier processing
    lines = content.split('\n')
    
    result = {}
    
    # If no headings found, process the whole content as one anonymous topic
    if not h1_positions:
        if content.strip():
            result["(No Topic)"] = content
        return result
    
    # Handle content before the first heading if any
    if h1_positions[0][0] > 0:
        preamble = '\n'.join(lines[:h1_positions[0][0]])
        if preamble.strip():
            result["(No Topic)"] = preamble
    
    # Process each heading and its content
    for i, (start_line, header_text) in enumerate(h1_positions):
        # Determine end line (either the next heading or end of document)
        if i < len(h1_positions) - 1:
            end_line = h1_positions[i + 1][0]
        else:
            end_line = len(lines)
        
        # Extract the content for this topic (including the heading line)
        chunk_content = '\n'.join(lines[start_line:end_line])
        result[header_text] = chunk_content
    
    return result


def analyze_content(content: str) -> Dict[str, int]:
    """
    Analyze content to count lines, words, and characters.
    
    Args:
        content: Text content to analyze
        
    Returns:
        Dictionary with line_count, word_count, and char_count
    """
    if not content:
        return {"line_count": 0, "word_count": 0, "char_count": 0}
    
    # Count lines (excluding empty trailing lines)
    lines = content.rstrip().split('\n')
    line_count = len(lines)
    
    # Count words and characters
    word_count = 0
    char_count = 0
    
    for line in lines:
        words = line.split()
        word_count += len(words)
        char_count += len(line)
    
    return {
        "line_count": line_count,
        "word_count": word_count,
        "char_count": char_count
    }


def process_document(filepath: str, topics_of_interest: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
    """
    Process a Markdown document and return analytics per topic.
    
    Args:
        filepath: Path to the Markdown file
        topics_of_interest: Optional list of topics to filter results
        
    Returns:
        Dictionary mapping topics to their analytics
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
    except Exception as e:
        raise DocumentAnalyticsException(f"Error reading file {filepath}: {str(e)}")
    
    # Extract topics from document
    topic_content = extract_topics(content)
    
    # Calculate analytics for each topic
    results = {}
    
    # Convert topics_of_interest to lowercase for case-insensitive comparison
    topics_lower = [t.lower() for t in topics_of_interest] if topics_of_interest else None
    
    for topic, topic_text in topic_content.items():
        # Skip topics that aren't in the topics_of_interest list, if provided
        # Use case-insensitive comparison
        if topics_of_interest and topic.lower() not in topics_lower:
            continue
        
        analytics = analyze_content(topic_text)
        results[topic] = analytics
    
    return results