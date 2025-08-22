# generate_puzzles.py - Save this as ONE file and run it!

import random
from collections import Counter

def load_words(filename='words.txt'):
    """Load words from file"""
    try:
        with open(filename, 'r') as f:
            words = [line.strip().upper() for line in f 
                    if len(line.strip()) == 5 and line.strip().isalpha()]
        print(f"✅ Loaded {len(words)} words from {filename}")
        return words
    except FileNotFoundError:
        print(f"❌ {filename} not found, using fallback words")
        return ["STORE", "STARE", "STEAM", "STEAL", "TIGER", "CHAIR", "HOUSE", "BREAD", "MAGIC"]

def can_make_word(word, available_letters):
    """Check if word can be made from available letters"""
    available_count = Counter(available_letters)
    word_count = Counter(word)
    
    for letter, needed in word_count.items():
        if available_count.get(letter, 0) < needed:
            return False
    return True

def generate_puzzle(answer_word, all_words):
    """Generate one puzzle"""
    
    answer_word = answer_word.upper()
    featured_letter = random.choice(answer_word)  # Pick random letter as featured
    
    # Start with answer word letters
    letter_pool = list(answer_word)
    
    # Add random common letters to reach 12
    common_letters = ['E', 'A', 'R', 'I', 'O', 'T', 'N', 'S', 'L', 'C', 'U', 'D', 'P', 'M', 'H', 'G', 'B', 'F', 'Y', 'W']
    
    while len(letter_pool) < 12:
        letter = random.choice(common_letters)
        if letter_pool.count(letter) < 3:  # Max 3 of any letter
            letter_pool.append(letter)
    
    # Scramble completely
    random.shuffle(letter_pool)
    
    # Find valid words that use featured letter
    valid_words = []
    for word in all_words:
        if featured_letter in word and can_make_word(word, letter_pool):
            valid_words.append(word)
    
    return {
        'featured_letter': featured_letter,
        'answer': answer_word,
        'available_letters': letter_pool,
        'valid_words': valid_words,
        'difficulty': len(valid_words)
    }

def main():
    """Main function - does everything"""
    
    print("🧩 Letter Puzzle Generator for Cafe Game")
    print("=" * 50)
    
    # Load words
    words = load_words()
    
    # Ask how many puzzles
    try:
        count = int(input("How many puzzles? (default 100): ") or "100")
    except ValueError:
        count = 100
    
    # Generate puzzles
    puzzles = []
    print(f"Generating {count} puzzles...")
    
    for i in range(count):
        answer_word = random.choice(words)
        puzzle = generate_puzzle(answer_word, words)
        puzzles.append(puzzle)
        
        if (i + 1) % 20 == 0:
            print(f"Generated {i + 1}/{count} puzzles...")
    
    # Save to file
    with open('letter_puzzles.txt', 'w') as f:
        f.write("# Generated Letter Puzzle Variations - FULLY SCRAMBLED\n")
        f.write("# Format: FEATURED_LETTER|ANSWER|AVAILABLE_LETTERS\n\n")
        
        for i, puzzle in enumerate(puzzles, 1):
            examples = puzzle['valid_words'][:5] if puzzle['valid_words'] else [puzzle['answer']]
            f.write(f"# Puzzle {i}: {puzzle['difficulty']} words with '{puzzle['featured_letter']}'\n")
            f.write(f"# Examples: {', '.join(examples)}\n")
            
            letters_str = ','.join(puzzle['available_letters'])
            f.write(f"{puzzle['featured_letter']}|{puzzle['answer']}|{letters_str}\n\n")
    
    # Show results
    difficulties = [p['difficulty'] for p in puzzles]
    print(f"\n✅ SUCCESS!")
    print(f"📁 Generated {len(puzzles)} puzzles in 'letter_puzzles.txt'")
    print(f"📊 Average difficulty: {sum(difficulties) / len(difficulties):.1f} words")
    print(f"📊 Range: {min(difficulties)} - {max(difficulties)} words")
    
    # Show sample
    sample = puzzles[0]
    print(f"\n📋 SAMPLE PUZZLE:")
    print(f"   Featured: {sample['featured_letter']}")
    print(f"   Answer: {sample['answer']}")
    print(f"   Letters: {', '.join(sample['available_letters'])}")
    print(f"   Valid words: {', '.join(sample['valid_words'][:3])}...")

if __name__ == "__main__":
    main()