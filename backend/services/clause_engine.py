"""
Clause Detection Engine
Implements ASC-606 focused clause taxonomy and detection
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ClauseType(Enum):
    ACCEPTANCE = "acceptance"
    PAYMENT_TERMS = "payment_terms"
    TERMINATION = "termination"
    PERFORMANCE_OBLIGATIONS = "performance_obligations"
    VARIABLE_CONSIDERATION = "variable_consideration"
    OVER_TIME_INDICATORS = "over_time_indicators"
    CONTRACT_MODIFICATION = "contract_modification"
    IP_TRANSFER = "ip_transfer"
    WARRANTY = "warranty"
    LIABILITY = "liability"

@dataclass
class ClausePattern:
    """Pattern for detecting specific clause types"""
    clause_type: ClauseType
    keywords: List[str]
    patterns: List[str]
    confidence_boosters: List[str]
    confidence_reducers: List[str]

class ClauseEngine:
    """Engine for detecting and analyzing ASC-606 relevant clauses"""
    
    def __init__(self):
        self.clause_patterns = self._initialize_clause_patterns()
        self.asc_606_taxonomy = self._initialize_asc_606_taxonomy()
    
    def _initialize_clause_patterns(self) -> List[ClausePattern]:
        """Initialize clause detection patterns"""
        return [
            ClausePattern(
                clause_type=ClauseType.ACCEPTANCE,
                keywords=["accept", "approve", "examine", "inspect", "review", "approval"],
                patterns=[
                    r"within\s+\d+\s+days?\s+(?:of|from)\s+(?:delivery|receipt|completion)",
                    r"customer\s+shall\s+(?:examine|inspect|review)",
                    r"acceptance\s+criteria",
                    r"remedy\s+(?:and\s+)?re-delivery"
                ],
                confidence_boosters=["30 days", "acceptance window", "remedy", "re-delivery"],
                confidence_reducers=["automatic acceptance", "deemed accepted"]
            ),
            ClausePattern(
                clause_type=ClauseType.PAYMENT_TERMS,
                keywords=["payment", "invoice", "due", "payable", "billing"],
                patterns=[
                    r"payment\s+(?:terms|conditions)",
                    r"within\s+\d+\s+days?\s+(?:of|from)\s+(?:invoice|receipt)",
                    r"net\s+\d+\s+days?",
                    r"payment\s+due\s+(?:upon|on)"
                ],
                confidence_boosters=["30 days", "net 30", "payment terms", "invoice"],
                confidence_reducers=["advance payment", "prepayment"]
            ),
            ClausePattern(
                clause_type=ClauseType.TERMINATION,
                keywords=["terminate", "termination", "cancel", "end", "expire"],
                patterns=[
                    r"early\s+termination\s+(?:payment|fee)",
                    r"termination\s+(?:for\s+)?convenience",
                    r"termination\s+penalty",
                    r"unamortized\s+costs"
                ],
                confidence_boosters=["early termination", "penalty", "unamortized", "convenience"],
                confidence_reducers=["mutual termination", "natural expiration"]
            ),
            ClausePattern(
                clause_type=ClauseType.PERFORMANCE_OBLIGATIONS,
                keywords=["deliver", "obligation", "service", "work", "deliverable"],
                patterns=[
                    r"performance\s+obligations?",
                    r"distinct\s+(?:goods|services)",
                    r"deliverables?",
                    r"work\s+product"
                ],
                confidence_boosters=["distinct", "performance obligation", "deliverable"],
                confidence_reducers=["ongoing support", "maintenance"]
            ),
            ClausePattern(
                clause_type=ClauseType.VARIABLE_CONSIDERATION,
                keywords=["variable", "contingent", "bonus", "penalty", "adjustment"],
                patterns=[
                    r"variable\s+consideration",
                    r"contingent\s+(?:fee|payment)",
                    r"performance\s+bonus",
                    r"price\s+adjustment"
                ],
                confidence_boosters=["variable consideration", "contingent", "bonus", "penalty"],
                confidence_reducers=["fixed price", "lump sum"]
            ),
            ClausePattern(
                clause_type=ClauseType.OVER_TIME_INDICATORS,
                keywords=["milestone", "progress", "over time", "continuous"],
                patterns=[
                    r"milestone\s+(?:payment|delivery)",
                    r"progress\s+(?:payment|billing)",
                    r"over\s+time",
                    r"continuous\s+(?:service|performance)"
                ],
                confidence_boosters=["milestone", "progress", "over time", "continuous"],
                confidence_reducers=["point in time", "upon delivery"]
            ),
            ClausePattern(
                clause_type=ClauseType.CONTRACT_MODIFICATION,
                keywords=["modification", "amendment", "change", "addendum"],
                patterns=[
                    r"contract\s+modification",
                    r"amendment\s+(?:to|of)",
                    r"change\s+order",
                    r"work\s+order"
                ],
                confidence_boosters=["modification", "amendment", "change order", "work order"],
                confidence_reducers=["original contract", "base agreement"]
            ),
            ClausePattern(
                clause_type=ClauseType.IP_TRANSFER,
                keywords=["intellectual property", "ownership", "license", "transfer"],
                patterns=[
                    r"intellectual\s+property",
                    r"ownership\s+(?:of|in)",
                    r"license\s+(?:to|from)",
                    r"transfer\s+(?:of|title)"
                ],
                confidence_boosters=["intellectual property", "ownership", "license", "transfer"],
                confidence_reducers=["confidential information", "trade secrets"]
            ),
            ClausePattern(
                clause_type=ClauseType.WARRANTY,
                keywords=["warranty", "guarantee", "defect", "remedy"],
                patterns=[
                    r"warranty\s+(?:period|terms)",
                    r"defect\s+(?:in|of)",
                    r"remedy\s+(?:for|of)",
                    r"guarantee\s+(?:of|for)"
                ],
                confidence_boosters=["warranty", "defect", "remedy", "guarantee"],
                confidence_reducers=["disclaimer", "as-is"]
            ),
            ClausePattern(
                clause_type=ClauseType.LIABILITY,
                keywords=["liability", "damages", "indemnify", "hold harmless"],
                patterns=[
                    r"liability\s+(?:for|of)",
                    r"indemnify\s+(?:and\s+)?hold\s+harmless",
                    r"damages\s+(?:for|of)",
                    r"limitation\s+(?:of\s+)?liability"
                ],
                confidence_boosters=["liability", "indemnify", "hold harmless", "damages"],
                confidence_reducers=["no liability", "disclaimer"]
            )
        ]
    
    def _initialize_asc_606_taxonomy(self) -> Dict[str, Any]:
        """Initialize ASC-606 clause taxonomy"""
        return {
            "step_1_identify_contract": {
                "clause_types": [ClauseType.ACCEPTANCE, ClauseType.PAYMENT_TERMS],
                "keywords": ["approved", "committed", "enforceable", "payment terms"],
                "description": "Contract identification and enforceability"
            },
            "step_2_identify_obligations": {
                "clause_types": [ClauseType.PERFORMANCE_OBLIGATIONS],
                "keywords": ["distinct", "performance obligation", "deliverable"],
                "description": "Distinct performance obligations"
            },
            "step_3_determine_price": {
                "clause_types": [ClauseType.PAYMENT_TERMS, ClauseType.VARIABLE_CONSIDERATION],
                "keywords": ["transaction price", "variable consideration", "constraints"],
                "description": "Transaction price determination"
            },
            "step_4_allocate_price": {
                "clause_types": [ClauseType.PERFORMANCE_OBLIGATIONS],
                "keywords": ["allocation", "standalone price", "relative value"],
                "description": "Price allocation to obligations"
            },
            "step_5_recognize_revenue": {
                "clause_types": [ClauseType.ACCEPTANCE, ClauseType.OVER_TIME_INDICATORS],
                "keywords": ["over time", "point in time", "control transfer"],
                "description": "Revenue recognition timing"
            }
        }
    
    def detect_clauses(self, document_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect ASC-606 relevant clauses in document sections"""
        detected_clauses = []
        
        for section in document_sections:
            content = section.get("content", "")
            section_name = section.get("section_name", "")
            page_number = section.get("page_number", 1)
            
            # Analyze each clause pattern
            for pattern in self.clause_patterns:
                clause_hits = self._analyze_section_for_pattern(
                    content, section_name, page_number, pattern
                )
                detected_clauses.extend(clause_hits)
        
        # Remove duplicates and sort by confidence
        unique_clauses = self._deduplicate_clauses(detected_clauses)
        return sorted(unique_clauses, key=lambda x: x["confidence_score"], reverse=True)
    
    def _analyze_section_for_pattern(
        self, 
        content: str, 
        section_name: str, 
        page_number: int, 
        pattern: ClausePattern
    ) -> List[Dict[str, Any]]:
        """Analyze a section for a specific clause pattern"""
        hits = []
        content_lower = content.lower()
        
        # Check for keyword matches
        keyword_matches = sum(1 for keyword in pattern.keywords if keyword in content_lower)
        if keyword_matches == 0:
            return hits
        
        # Check for pattern matches
        pattern_matches = []
        for regex_pattern in pattern.patterns:
            matches = re.finditer(regex_pattern, content, re.IGNORECASE)
            for match in matches:
                pattern_matches.append({
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        # Calculate confidence score
        confidence = self._calculate_confidence_score(
            content, pattern, keyword_matches, pattern_matches
        )
        
        if confidence > 0.3:  # Minimum confidence threshold
            hits.append({
                "clause_type": pattern.clause_type.value,
                "clause_text": self._extract_clause_text(content, pattern_matches),
                "page_number": page_number,
                "section": section_name,
                "confidence_score": confidence,
                "keyword_matches": keyword_matches,
                "pattern_matches": len(pattern_matches),
                "relevance_indicators": self._get_relevance_indicators(content, pattern)
            })
        
        return hits
    
    def _calculate_confidence_score(
        self, 
        content: str, 
        pattern: ClausePattern, 
        keyword_matches: int, 
        pattern_matches: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for a clause detection"""
        base_score = min(keyword_matches / len(pattern.keywords), 1.0)
        
        # Boost for pattern matches
        pattern_boost = min(len(pattern_matches) * 0.2, 0.4)
        
        # Boost for confidence boosters
        booster_matches = sum(1 for booster in pattern.confidence_boosters 
                             if booster.lower() in content.lower())
        booster_boost = min(booster_matches * 0.1, 0.3)
        
        # Reduce for confidence reducers
        reducer_matches = sum(1 for reducer in pattern.confidence_reducers 
                             if reducer.lower() in content.lower())
        reducer_penalty = min(reducer_matches * 0.15, 0.3)
        
        # Calculate final score
        final_score = base_score + pattern_boost + booster_boost - reducer_penalty
        return max(0.0, min(1.0, final_score))
    
    def _extract_clause_text(self, content: str, pattern_matches: List[Dict[str, Any]]) -> str:
        """Extract the most relevant clause text"""
        if not pattern_matches:
            # Return first sentence if no specific matches
            sentences = content.split('.')
            return sentences[0].strip() + '.' if sentences else content[:200]
        
        # Return the longest match
        longest_match = max(pattern_matches, key=lambda x: len(x["text"]))
        return longest_match["text"]
    
    def _get_relevance_indicators(self, content: str, pattern: ClausePattern) -> List[str]:
        """Get indicators of clause relevance"""
        indicators = []
        content_lower = content.lower()
        
        for booster in pattern.confidence_boosters:
            if booster.lower() in content_lower:
                indicators.append(booster)
        
        return indicators
    
    def _deduplicate_clauses(self, clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate clauses based on similarity"""
        unique_clauses = []
        
        for clause in clauses:
            is_duplicate = False
            for existing in unique_clauses:
                if (clause["clause_type"] == existing["clause_type"] and
                    clause["page_number"] == existing["page_number"] and
                    self._calculate_text_similarity(clause["clause_text"], existing["clause_text"]) > 0.8):
                    is_duplicate = True
                    # Keep the one with higher confidence
                    if clause["confidence_score"] > existing["confidence_score"]:
                        unique_clauses.remove(existing)
                        unique_clauses.append(clause)
                    break
            
            if not is_duplicate:
                unique_clauses.append(clause)
        
        return unique_clauses
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def map_clauses_to_asc_606_questions(
        self, 
        clauses: List[Dict[str, Any]], 
        questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Map detected clauses to ASC-606 questions"""
        mapped_answers = []
        
        for question in questions:
            question_id = question["id"]
            question_text = question["text"]
            relevant_clause_types = question.get("clause_types", [])
            
            # Find relevant clauses
            relevant_clauses = [
                clause for clause in clauses 
                if clause["clause_type"] in relevant_clause_types
            ]
            
            # Determine suggested answer
            suggested_answer = self._determine_suggested_answer(relevant_clauses, question_id)
            confidence = self._calculate_question_confidence(relevant_clauses)
            
            mapped_answers.append({
                "question_id": question_id,
                "question_text": question_text,
                "suggested_answer": suggested_answer,
                "confidence": confidence,
                "clause_hits": relevant_clauses,
                "alternative_hits": self._find_alternative_hits(clauses, relevant_clause_types)
            })
        
        return mapped_answers
    
    def _determine_suggested_answer(self, clauses: List[Dict[str, Any]], question_id: str) -> str:
        """Determine suggested answer based on detected clauses"""
        if not clauses:
            return "No"
        
        # Question-specific logic
        if "acceptance" in question_id:
            return "Yes" if any("accept" in clause["clause_text"].lower() for clause in clauses) else "No"
        elif "payment" in question_id:
            return "Yes" if any("payment" in clause["clause_text"].lower() for clause in clauses) else "No"
        elif "termination" in question_id:
            return "Yes" if any("termination" in clause["clause_text"].lower() for clause in clauses) else "No"
        elif "variable" in question_id:
            return "Yes" if any("variable" in clause["clause_text"].lower() for clause in clauses) else "No"
        else:
            return "Yes" if clauses else "No"
    
    def _calculate_question_confidence(self, clauses: List[Dict[str, Any]]) -> float:
        """Calculate confidence for a question based on clause hits"""
        if not clauses:
            return 0.0
        
        # Average confidence of relevant clauses
        avg_confidence = sum(clause["confidence_score"] for clause in clauses) / len(clauses)
        
        # Boost for multiple supporting clauses
        multiplicity_boost = min(len(clauses) * 0.1, 0.3)
        
        return min(1.0, avg_confidence + multiplicity_boost)
    
    def _find_alternative_hits(
        self, 
        all_clauses: List[Dict[str, Any]], 
        relevant_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Find alternative clause hits that might be relevant"""
        alternatives = []
        
        for clause in all_clauses:
            if clause["clause_type"] not in relevant_types and clause["confidence_score"] > 0.5:
                alternatives.append(clause)
        
        return sorted(alternatives, key=lambda x: x["confidence_score"], reverse=True)[:3]
