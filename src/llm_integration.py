import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.schema import Document
from langchain.chains import LLMChain

from .config import config
from .database import db_manager
from .embeddings import embedding_generator
from .markdown_storage import MarkdownStorage

logger = logging.getLogger(__name__)


class LLMIntegration:
    """Integrate LLM capabilities for email analysis and search"""
    
    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.chat_model = ChatOpenAI(
            temperature=0.3,
            model="gpt-4o-mini",
            api_key=config.OPENAI_API_KEY
        )
        self.markdown_storage = MarkdownStorage()
    
    def semantic_search(self, 
                       query: str, 
                       limit: int = 10,
                       date_from: Optional[datetime] = None,
                       date_to: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Perform semantic search on emails"""
        # Generate query embedding
        query_embedding = embedding_generator.generate_embedding(query)
        
        # Search in database
        if date_from or date_to:
            results = db_manager.hybrid_search(
                query_embedding, query, limit, date_from, date_to
            )
        else:
            results = db_manager.search_similar_emails(query_embedding, limit)
        
        # Enrich results with markdown content
        enriched_results = []
        for result in results:
            if result.get('markdown_path'):
                email_content = self.markdown_storage.load_email(result['message_id'])
                if email_content:
                    result['content'] = email_content['content']
                    result['frontmatter'] = email_content['frontmatter']
            enriched_results.append(result)
        
        return enriched_results
    
    def categorize_emails(self, email_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Categorize emails using LLM"""
        categorization_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """You are an email categorization assistant. Analyze the email and provide:
                1. Primary category (one of: Work, Personal, Finance, Shopping, Travel, Marketing, Spam, Other)
                2. Subcategory (more specific classification)
                3. Priority level (High, Medium, Low)
                4. Action required (Yes/No)
                5. Brief summary (max 50 words)
                
                Respond in JSON format only."""
            ),
            HumanMessagePromptTemplate.from_template(
                "Email content:\n{email_content}"
            )
        ])
        
        chain = LLMChain(llm=self.chat_model, prompt=categorization_prompt)
        results = {}
        
        for email_id in email_ids:
            try:
                # Get email content
                email = db_manager.get_email_by_id(email_id)
                if not email:
                    continue
                
                content = email.get('body_markdown') or email.get('body_plain', '')
                if not content:
                    continue
                
                # Truncate content for categorization
                content = content[:2000]
                
                # Run categorization
                response = chain.run(email_content=content)
                
                # Parse JSON response
                try:
                    categorization = json.loads(response)
                    results[email_id] = categorization
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse categorization for email {email_id}")
                    results[email_id] = {
                        "error": "Failed to parse response",
                        "raw_response": response
                    }
            
            except Exception as e:
                logger.error(f"Error categorizing email {email_id}: {e}")
                results[email_id] = {"error": str(e)}
        
        return results
    
    def summarize_thread(self, thread_id: str) -> Dict[str, Any]:
        """Summarize an email thread"""
        # Get all emails in thread
        emails = db_manager.get_emails_by_thread(thread_id)
        
        if not emails:
            return {"error": "No emails found in thread"}
        
        # Sort by date
        emails.sort(key=lambda x: x.get('date') or datetime.min)
        
        # Build thread context
        thread_context = []
        for email in emails:
            thread_context.append(f"""
From: {email.get('sender_name', email.get('sender', 'Unknown'))}
Date: {email.get('date', 'Unknown')}
Subject: {email.get('subject', 'No Subject')}

{email.get('body_plain', '')[:500]}...
---
""")
        
        full_context = "\n".join(thread_context)
        
        # Summarize using LLM
        summary_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """You are an email thread summarization assistant. 
                Provide a concise summary that includes:
                1. Main topic of discussion
                2. Key participants
                3. Important decisions or action items
                4. Current status
                5. Next steps if any
                
                Keep the summary under 200 words."""
            ),
            HumanMessagePromptTemplate.from_template(
                "Email thread:\n{thread_context}"
            )
        ])
        
        chain = LLMChain(llm=self.chat_model, prompt=summary_prompt)
        
        try:
            summary = chain.run(thread_context=full_context)
            
            return {
                "thread_id": thread_id,
                "email_count": len(emails),
                "date_range": {
                    "start": emails[0].get('date'),
                    "end": emails[-1].get('date')
                },
                "participants": list(set(e.get('sender') for e in emails if e.get('sender'))),
                "summary": summary
            }
        
        except Exception as e:
            logger.error(f"Error summarizing thread {thread_id}: {e}")
            return {"error": str(e)}
    
    def extract_action_items(self, email_ids: List[int]) -> List[Dict[str, Any]]:
        """Extract action items from emails"""
        action_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """You are an action item extraction assistant.
                Extract any action items, tasks, or commitments from the email.
                For each action item, provide:
                1. Description of the task
                2. Who is responsible (if mentioned)
                3. Due date (if mentioned)
                4. Priority (inferred from context)
                
                Respond in JSON format as a list of action items.
                If no action items found, return empty list."""
            ),
            HumanMessagePromptTemplate.from_template(
                "Email content:\n{email_content}"
            )
        ])
        
        chain = LLMChain(llm=self.chat_model, prompt=action_prompt)
        all_actions = []
        
        for email_id in email_ids:
            try:
                email = db_manager.get_email_by_id(email_id)
                if not email:
                    continue
                
                content = f"""
Subject: {email.get('subject', '')}
From: {email.get('sender', '')}
Date: {email.get('date', '')}

{email.get('body_plain', '')[:3000]}
"""
                
                response = chain.run(email_content=content)
                
                try:
                    actions = json.loads(response)
                    for action in actions:
                        action['email_id'] = email_id
                        action['email_subject'] = email.get('subject')
                        action['email_date'] = email.get('date')
                        all_actions.append(action)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse actions for email {email_id}")
            
            except Exception as e:
                logger.error(f"Error extracting actions from email {email_id}: {e}")
        
        return all_actions
    
    def answer_question(self, question: str, context_limit: int = 5) -> Dict[str, Any]:
        """Answer questions about emails using RAG"""
        # Search for relevant emails
        search_results = self.semantic_search(question, limit=context_limit)
        
        if not search_results:
            return {
                "question": question,
                "answer": "I couldn't find any relevant emails to answer your question.",
                "sources": []
            }
        
        # Build context from search results
        context_parts = []
        sources = []
        
        for result in search_results:
            context_parts.append(f"""
Email ID: {result['message_id']}
Subject: {result.get('subject', 'No Subject')}
From: {result.get('sender', 'Unknown')}
Date: {result.get('date', 'Unknown')}
Relevance: {result.get('similarity', 0):.2f}

Content:
{result.get('content', '')[:1000]}...
---
""")
            sources.append({
                "message_id": result['message_id'],
                "subject": result.get('subject'),
                "sender": result.get('sender'),
                "date": str(result.get('date')),
                "similarity": result.get('similarity', 0)
            })
        
        context = "\n".join(context_parts)
        
        # Answer using LLM
        qa_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """You are a helpful email assistant. Answer the user's question based on the provided email context.
                Be specific and cite which emails you're referencing.
                If the context doesn't contain enough information, say so.
                Keep your answer concise and relevant."""
            ),
            HumanMessagePromptTemplate.from_template(
                """Context emails:
{context}

Question: {question}

Answer:"""
            )
        ])
        
        chain = LLMChain(llm=self.chat_model, prompt=qa_prompt)
        
        try:
            answer = chain.run(context=context, question=question)
            
            return {
                "question": question,
                "answer": answer,
                "sources": sources,
                "context_email_count": len(search_results)
            }
        
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                "question": question,
                "answer": f"An error occurred: {str(e)}",
                "sources": sources
            }
    
    def generate_email_insights(self, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate insights from email patterns"""
        # This would analyze patterns like:
        # - Most frequent senders
        # - Email volume trends
        # - Common topics
        # - Response patterns
        # Implementation depends on specific requirements
        
        return {
            "insights": "Email insights generation not yet implemented",
            "date_range": {
                "start": start_date,
                "end": end_date
            }
        }


# Global LLM integration instance
llm_integration = LLMIntegration()