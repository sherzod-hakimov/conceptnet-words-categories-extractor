import gzip
import csv
import json
import sys
import os
from collections import defaultdict
from typing import Dict, List, Set, Optional

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
# Path to the ConceptNet 5.7 assertions file
CONCEPTNET_FILE = '/Users/sherzodhakimov/Downloads/conceptnet-assertions-5.7.0.csv.gz'

# Source language
SOURCE_LANG = 'en'

# Relations to extract hierarchy
# /r/IsA - X is a type of Y (e.g., "cat" IsA "pet")
# /r/InstanceOf - X is an instance of Y (e.g., "Fluffy" InstanceOf "cat")
HIERARCHY_RELATIONS = {'/r/IsA', '/r/InstanceOf'}

# Minimum weight to consider valid
MIN_WEIGHT = 1.0

# Filter by POS? Set to 'n' for nouns only, None for all
POS_FILTER = 'n'

# Output files
HIERARCHY_OUTPUT = 'category_hierarchy.json'
FLAT_OUTPUT = 'category_flat.json'
STATS_OUTPUT = 'category_stats.json'

# -------------------------------------------------------------------
# SYSTEM SETUP
# -------------------------------------------------------------------
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)


class CategoryHierarchyExtractor:
    """
    Extracts hierarchical category relationships from ConceptNet.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.relations = HIERARCHY_RELATIONS
        
        # child -> set of parents (e.g., "cat" -> {"pet", "animal", "mammal"})
        self.child_to_parents = defaultdict(set)
        
        # parent -> set of children (e.g., "pet" -> {"cat", "dog", "bird"})
        self.parent_to_children = defaultdict(set)
        
        # All concepts found
        self.all_concepts = set()

    def parse_uri(self, uri: str) -> Optional[dict]:
        """
        Parses a ConceptNet URI.
        """
        if not uri.startswith('/c/'):
            return None

        parts = uri.split('/')
        if len(parts) < 4:
            return None

        data = {
            'lang': parts[2],
            'text': parts[3].replace('_', ' '),
            'pos': parts[4] if len(parts) > 4 else None
        }

        return data

    def extract(self) -> None:
        """
        Extracts hierarchy relationships from ConceptNet.
        """
        print(f"Reading {self.filepath}...")
        print(f"Extracting hierarchical relationships for '{SOURCE_LANG}'...")

        if not os.path.exists(self.filepath):
            print(f"Error: File {self.filepath} not found.")
            return

        line_count = 0
        relations_found = 0

        try:
            with gzip.open(self.filepath, 'rt', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)

                for row in reader:
                    line_count += 1
                    if line_count % 1_000_000 == 0:
                        print(f"Processed {line_count:,} assertions, found {relations_found:,} relations...", end='\r')

                    if len(row) < 5:
                        continue

                    uri, relation, start_node, end_node, json_metadata = row

                    # Filter by relation
                    if relation not in self.relations:
                        continue

                    # Parse URIs
                    start = self.parse_uri(start_node)
                    end = self.parse_uri(end_node)

                    if not start or not end:
                        continue

                    # Only process if both are in source language
                    if start['lang'] != SOURCE_LANG or end['lang'] != SOURCE_LANG:
                        continue

                    # Filter by POS if specified
                    if POS_FILTER:
                        if start['pos'] != POS_FILTER or end['pos'] != POS_FILTER:
                            continue

                    # Check weight
                    try:
                        meta = json.loads(json_metadata)
                        if meta.get('weight', 0) < MIN_WEIGHT:
                            continue
                    except json.JSONDecodeError:
                        continue

                    # Extract relationship: start IsA end
                    # e.g., "cat" IsA "pet" means cat is a child of pet
                    child = start['text']
                    parent = end['text']

                    self.child_to_parents[child].add(parent)
                    self.parent_to_children[parent].add(child)
                    self.all_concepts.add(child)
                    self.all_concepts.add(parent)
                    
                    relations_found += 1

        except KeyboardInterrupt:
            print("\nProcessing interrupted by user.")
        except Exception as e:
            print(f"\nCritical Error: {e}")
            import traceback
            traceback.print_exc()

        print(f"\nComplete. Processed {line_count:,} assertions.")
        print(f"Found {relations_found:,} hierarchical relations.")
        print(f"Total unique concepts: {len(self.all_concepts):,}")

    def get_all_ancestors(self, concept: str, visited: Set[str] = None) -> Set[str]:
        """
        Gets all ancestors (parents, grandparents, etc.) of a concept.
        """
        if visited is None:
            visited = set()
        
        if concept in visited:
            return set()
        
        visited.add(concept)
        ancestors = set()
        
        for parent in self.child_to_parents.get(concept, []):
            ancestors.add(parent)
            ancestors.update(self.get_all_ancestors(parent, visited))
        
        return ancestors

    def get_all_descendants(self, concept: str, visited: Set[str] = None) -> Set[str]:
        """
        Gets all descendants (children, grandchildren, etc.) of a concept.
        """
        if visited is None:
            visited = set()
        
        if concept in visited:
            return set()
        
        visited.add(concept)
        descendants = set()
        
        for child in self.parent_to_children.get(concept, []):
            descendants.add(child)
            descendants.update(self.get_all_descendants(child, visited))
        
        return descendants

    def find_root_categories(self, min_children: int = 10) -> List[str]:
        """
        Finds potential root categories (concepts with many children but few/no parents).
        """
        roots = []
        
        for concept in self.parent_to_children.keys():
            num_children = len(self.get_all_descendants(concept))
            num_parents = len(self.child_to_parents.get(concept, []))
            
            # Root candidates: many descendants, few parents
            if num_children >= min_children and num_parents <= 2:
                roots.append((concept, num_children, num_parents))
        
        # Sort by number of descendants
        roots.sort(key=lambda x: x[1], reverse=True)
        return roots

    def build_tree(self, root: str, max_depth: int = 5) -> dict:
        """
        Builds a tree structure starting from a root concept.
        """
        def _build_subtree(concept: str, depth: int, visited: Set[str]) -> dict:
            if depth >= max_depth or concept in visited:
                return None
            
            visited.add(concept)
            
            children = self.parent_to_children.get(concept, set())
            if not children:
                return None
            
            tree = {}
            for child in sorted(children):
                subtree = _build_subtree(child, depth + 1, visited.copy())
                if subtree:
                    tree[child] = subtree
                else:
                    tree[child] = {}
            
            return tree if tree else {}
        
        return {root: _build_subtree(root, 0, set())}

    def get_leaf_concepts(self) -> Set[str]:
        """
        Gets concepts that have no children (leaf nodes).
        """
        return self.all_concepts - set(self.parent_to_children.keys())

    def export_hierarchy(self) -> dict:
        """
        Exports the full hierarchy structure.
        """
        return {
            'parent_to_children': {
                parent: sorted(list(children)) 
                for parent, children in self.parent_to_children.items()
            },
            'child_to_parents': {
                child: sorted(list(parents)) 
                for child, parents in self.child_to_parents.items()
            }
        }

    def export_flat_categories(self, top_n: int = 100) -> dict:
        """
        Exports a flat list of top categories with their direct and indirect children.
        """
        # Find concepts with most children
        category_sizes = []
        for concept in self.parent_to_children.keys():
            all_descendants = self.get_all_descendants(concept)
            direct_children = self.parent_to_children[concept]
            
            if len(all_descendants) >= 5:  # At least 5 total descendants
                category_sizes.append({
                    'category': concept,
                    'direct_children': len(direct_children),
                    'total_descendants': len(all_descendants)
                })
        
        # Sort by total descendants
        category_sizes.sort(key=lambda x: x['total_descendants'], reverse=True)
        
        # Build output
        result = {}
        for item in category_sizes[:top_n]:
            cat = item['category']
            result[cat] = {
                'direct_children': sorted(list(self.parent_to_children[cat])),
                'all_descendants': sorted(list(self.get_all_descendants(cat))),
                'stats': {
                    'direct_children_count': item['direct_children'],
                    'total_descendants_count': item['total_descendants'],
                    'parent_categories': sorted(list(self.child_to_parents.get(cat, [])))
                }
            }
        
        return result

    def export_stats(self) -> dict:
        """
        Exports statistics about the hierarchy.
        """
        leaf_concepts = self.get_leaf_concepts()
        
        # Find root categories
        roots = self.find_root_categories(min_children=10)
        
        return {
            'total_concepts': len(self.all_concepts),
            'total_parent_categories': len(self.parent_to_children),
            'total_child_concepts': len(self.child_to_parents),
            'leaf_concepts': len(leaf_concepts),
            'top_root_categories': [
                {'name': name, 'descendants': count, 'parents': parents}
                for name, count, parents in roots[:20]
            ],
            'sample_leaf_concepts': sorted(list(leaf_concepts))[:50]
        }


def print_tree(tree: dict, indent: int = 0, max_items: int = 10):
    """
    Pretty prints a tree structure.
    """
    for i, (key, value) in enumerate(tree.items()):
        if i >= max_items:
            remaining = len(tree) - max_items
            print("  " * indent + f"... and {remaining} more")
            break
        
        print("  " * indent + f"- {key}")
        if value and isinstance(value, dict):
            print_tree(value, indent + 1, max_items)


if __name__ == "__main__":
    extractor = CategoryHierarchyExtractor(CONCEPTNET_FILE)
    extractor.extract()

    print("\n" + "="*60)
    print("FINDING ROOT CATEGORIES")
    print("="*60)
    
    roots = extractor.find_root_categories(min_children=10)
    print(f"\nTop 20 root categories:")
    for i, (name, descendants, parents) in enumerate(roots[:20], 1):
        parent_str = f" (parents: {parents})" if parents > 0 else ""
        print(f"{i:2}. {name:25} - {descendants:5} descendants{parent_str}")

    # Export full hierarchy
    print(f"\nSaving full hierarchy to {HIERARCHY_OUTPUT}...")
    hierarchy = extractor.export_hierarchy()
    with open(HIERARCHY_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)

    # Export flat categories
    print(f"Saving flat categories to {FLAT_OUTPUT}...")
    flat_cats = extractor.export_flat_categories(top_n=100)
    with open(FLAT_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(flat_cats, f, ensure_ascii=False, indent=2)

    # Export statistics
    print(f"Saving statistics to {STATS_OUTPUT}...")
    stats = extractor.export_stats()
    with open(STATS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Show example trees
    print("\n" + "="*60)
    print("EXAMPLE CATEGORY TREES")
    print("="*60)
    
    example_categories = ['animal', 'vehicle', 'food', 'person', 'place']
    for cat in example_categories:
        if cat in extractor.parent_to_children:
            print(f"\n{cat.upper()} hierarchy:")
            tree = extractor.build_tree(cat, max_depth=3)
            print_tree(tree, max_items=8)

    print("\n" + "="*60)
    print(f"Done! Check the following files:")
    print(f"  - {HIERARCHY_OUTPUT} (full hierarchy)")
    print(f"  - {FLAT_OUTPUT} (top 100 categories with all their members)")
    print(f"  - {STATS_OUTPUT} (statistics)")
    print("="*60)
