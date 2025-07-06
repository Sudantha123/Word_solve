import logging
import os
import asyncio
import random
import re
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global userbot instance
_userbot_instance = None

class WordleUserBot:
    def __init__(self, api_id, api_hash, session_string):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.client = None
        self.active_games = {}  # chat_id: game_state
        self.word_list = []
        self.owner_bot_id = 7728440793
        self.load_words()

    def load_words(self):
        """Load 5-letter words from file"""
        try:
            with open('words.txt', 'r') as f:
                for line in f:
                    word = line.strip().lower()
                    if len(word) == 5 and word.isalpha():
                        self.word_list.append(word)
            logger.info(f"Loaded {len(self.word_list)} words for userbot")
        except FileNotFoundError:
            logger.error("words.txt file not found for userbot!")

    def get_random_word(self):
        """Get a random 5-letter word"""
        return random.choice(self.word_list).upper()

    def get_letter_frequency(self, words):
        """Get frequency of letters in remaining words"""
        freq = defaultdict(int)
        for word in words:
            for char in set(word):  # Use set to count each letter once per word
                freq[char] += 1
        return freq

    def score_word(self, word, letter_freq):
        """Score a word based on letter frequency"""
        score = 0
        used_letters = set()
        for char in word:
            if char not in used_letters:
                score += letter_freq[char]
                used_letters.add(char)
        return score

    def parse_wordle_result(self, message_text):
        """Parse Wordle result from bot response"""
        # Check for emoji patterns
        emoji_pattern = r'([🟥🟨🟩]\s*){5}'
        if re.search(emoji_pattern, message_text):
            return True
        return False

    def is_invalid_word_message(self, message_text):
        """Check if message indicates invalid word"""
        invalid_patterns = [
            "is not a valid word",
            "not a valid word",
            "invalid word"
        ]
        return any(pattern in message_text.lower() for pattern in invalid_patterns)

    def is_already_guessed_message(self, message_text):
        """Check if someone already guessed the word"""
        already_guessed_patterns = [
            "Someone has already guessed your word",
            "already guessed",
            "Please try another one"
        ]
        return any(pattern in message_text for pattern in already_guessed_patterns)

    def is_correct_guess_message(self, message_text):
        """Check if the guess was correct"""
        correct_patterns = [
            "Congrats! You guessed it correctly",
            "guessed correctly",
            "Start with /new"
        ]
        return any(pattern in message_text for pattern in correct_patterns)

    def is_new_game_started_message(self, message_text):
        """Check if a new game was started"""
        new_game_patterns = [
            "I've started a new Wordle",
            "New Wordle started",
            "Guess a 5-letter word",
            "new word is ready"
        ]
        return any(pattern in message_text for pattern in new_game_patterns)

    def extract_clues_from_message(self, message_text):
        """Extract clues from message with multiple guesses"""
        clues = []
        lines = message_text.strip().split('\n')

        # Mathematical Sans-Serif Bold Capital Letters mapping
        math_bold_to_regular = {
            '𝗔': 'A', '𝗕': 'B', '𝗖': 'C', '𝗗': 'D', '𝗘': 'E', '𝗙': 'F', '𝗚': 'G', '𝗛': 'H',
            '𝗜': 'I', '𝗝': 'J', '𝗞': 'K', '𝗟': 'L', '𝗠': 'M', '𝗡': 'N', '𝗢': 'O', '𝗣': 'P',
            '𝗤': 'Q', '𝗥': 'R', '𝗦': 'S', '𝗧': 'T', '𝗨': 'U', '𝗩': 'V', '𝗪': 'W', '𝗫': 'X',
            '𝗬': 'Y', '𝗭': 'Z'
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Pattern for Mathematical Sans-Serif Bold format
            pattern_math_bold = r'([🟥🟨🟩]\s*){5}\s*([𝗔-𝗭]{5})'
            match_math_bold = re.search(pattern_math_bold, line)

            if match_math_bold:
                emoji_part = line.split(match_math_bold.group(2))[0].strip()
                emoji_result = re.sub(r'\s+', '', emoji_part)
                math_bold_word = match_math_bold.group(2)
                guess_word = ''.join(math_bold_to_regular.get(char, char) for char in math_bold_word).lower()
                clues.append((guess_word, emoji_result))

        return clues

    def filter_words_by_clues(self, clues):
        """Filter words based on all collected clues with advanced logic"""
        if not clues:
            return self.word_list

        valid_words = []

        for word in self.word_list:
            is_valid = True

            # Track letters we know are in the word and their constraints
            required_letters = set()
            forbidden_letters = set()
            position_constraints = {}  # position -> required letter
            position_forbidden = {}    # position -> set of forbidden letters

            # Analyze all clues first
            for guess_word, emoji_result in clues:
                for i, (guess_char, emoji) in enumerate(zip(guess_word, emoji_result)):
                    if emoji == '🟩':  # Green - correct letter, correct position
                        position_constraints[i] = guess_char
                        required_letters.add(guess_char)
                    elif emoji == '🟨':  # Yellow - correct letter, wrong position
                        required_letters.add(guess_char)
                        if i not in position_forbidden:
                            position_forbidden[i] = set()
                        position_forbidden[i].add(guess_char)
                    elif emoji == '🟥':  # Red - letter not in word
                        # Only mark as forbidden if it's not required elsewhere
                        if guess_char not in required_letters:
                            forbidden_letters.add(guess_char)

            # Check if word satisfies all constraints
            # 1. Check required positions (green letters)
            for pos, required_char in position_constraints.items():
                if word[pos] != required_char:
                    is_valid = False
                    break

            if not is_valid:
                continue

            # 2. Check forbidden letters (red letters that aren't required)
            word_letters = set(word)
            if forbidden_letters & word_letters:
                is_valid = False
                continue

            # 3. Check required letters are present (yellow letters)
            if not required_letters.issubset(word_letters):
                is_valid = False
                continue

            # 4. Check position forbidden constraints (yellow letters can't be in wrong spots)
            for pos, forbidden_chars in position_forbidden.items():
                if word[pos] in forbidden_chars:
                    is_valid = False
                    break

            if is_valid:
                valid_words.append(word)

        return valid_words

    def get_best_guess(self, clues, used_words=None):
        """Get the best next guess based on clues using advanced strategy"""
        if used_words is None:
            used_words = set()

        valid_words = self.filter_words_by_clues(clues)

        # Remove already used words (convert both to lowercase for comparison)
        valid_words = [word for word in valid_words if word.lower() not in {w.lower() for w in used_words}]

        if not valid_words:
            # If no valid words left, try random words that haven't been used
            remaining_words = [word for word in self.word_list if word.lower() not in {w.lower() for w in used_words}]
            if remaining_words:
                return random.choice(remaining_words).upper()
            else:
                return self.get_random_word()

        if len(valid_words) == 1:
            return valid_words[0].upper()

        # If we have many options, prefer words with common letters and good coverage
        if len(valid_words) > 50:
            # Use high-frequency starting words for better elimination, but exclude used ones
            common_starters = ['arose', 'adieu', 'audio', 'ourie', 'louie', 'storm', 'court', 'plant', 'slice', 'crane']
            available_starters = [w for w in common_starters if w in self.word_list and w.lower() not in {word.lower() for word in used_words}]
            if available_starters and (not clues or len(clues) < 2):
                return available_starters[0].upper()

        # Calculate letter frequencies in remaining words
        letter_freq = self.get_letter_frequency(valid_words)

        # Advanced scoring: consider letter uniqueness and position variety
        def advanced_score(word):
            base_score = self.score_word(word, letter_freq)

            # Bonus for words with unique letters (avoid repeated letters early)
            unique_letters = len(set(word))
            uniqueness_bonus = unique_letters * 10

            # Bonus for common letter positions
            position_bonus = 0
            for i, char in enumerate(word):
                # Count how many remaining words have this letter in this position
                position_count = sum(1 for w in valid_words if w[i] == char)
                if position_count > len(valid_words) * 0.1:  # If >10% of words have this letter here
                    position_bonus += position_count

            return base_score + uniqueness_bonus + position_bonus

        # Score all words and return the best one
        best_word = max(valid_words, key=advanced_score)
        return best_word.upper()

    async def start(self):
        """Start the userbot client"""
        from telethon.sessions import StringSession
        self.client = TelegramClient(StringSession(self.session_string), self.api_id, self.api_hash)
        await self.client.start()
        logger.info("Userbot started successfully")

        # Add event handler for incoming messages
        @self.client.on(events.NewMessage)
        async def handle_message(event):
            if event.sender_id == self.owner_bot_id:
                await self.handle_bot_response(event)

    async def handle_bot_response(self, event):
        """Handle responses from the Wordle bot"""
        chat_id = event.chat_id
        message_text = event.message.message

        if chat_id not in self.active_games:
            return

        game_state = self.active_games[chat_id]

        # Check if word is invalid
        if self.is_invalid_word_message(message_text):
            logger.info(f"Invalid word in chat {chat_id}, trying another word")
            await asyncio.sleep(random.uniform(2, 4))

            # Send typing action
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 2))

            # Try to get a better word based on current clues
            used_words = game_state.get('used_words', set())
            next_guess = self.get_best_guess(game_state['clues'], used_words)
            if next_guess and next_guess.lower() not in used_words:
                game_state.setdefault('used_words', set()).add(next_guess.lower())
                await self.client.send_message(chat_id, next_guess)
                logger.info(f"Sent new word after invalid: {next_guess}")
            return

        # Check if someone already guessed
        if self.is_already_guessed_message(message_text):
            logger.info(f"Word already guessed in chat {chat_id}, trying another word")
            await asyncio.sleep(random.uniform(2, 4))

            # Send typing action
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 2))

            # Try to get a better word based on current clues
            used_words = game_state.get('used_words', set())
            next_guess = self.get_best_guess(game_state['clues'], used_words)
            if next_guess and next_guess.lower() not in used_words:
                game_state.setdefault('used_words', set()).add(next_guess.lower())
                await self.client.send_message(chat_id, next_guess)
                logger.info(f"Sent new word after already guessed: {next_guess}")
            else:
                logger.warning(f"Could not find new word for chat {chat_id}, all words may be used")
            return

        # Check if guess was correct
        if self.is_correct_guess_message(message_text):
            logger.info(f"Correct guess in chat {chat_id}, starting new round")
            # Add realistic delay before starting new game
            await asyncio.sleep(random.uniform(3, 6))

            # Send typing action
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 2))

            # Start new game
            await self.client.send_message(chat_id, "/new")
            game_state['clues'] = []
            game_state['used_words'] = set()  # Reset used words for new game

            # Wait for new game to start, then send first word
            await asyncio.sleep(random.uniform(2, 4))
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 2))

            # Send first guess for new game
            first_guess = self.get_best_guess([], set())
            if first_guess:
                game_state['used_words'].add(first_guess.lower())
                await self.client.send_message(chat_id, first_guess)
                logger.info(f"Started new round in chat {chat_id} with word: {first_guess}")
            return

        # Check if new game started (after /new command)
        if self.is_new_game_started_message(message_text):
            logger.info(f"New game started in chat {chat_id}")
            # Reset game state
            game_state['clues'] = []
            game_state['used_words'] = set()

            # Add realistic delay before first guess
            await asyncio.sleep(random.uniform(2, 5))
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 2))

            # Send first guess for new game
            first_guess = self.get_best_guess([], set())
            if first_guess:
                game_state['used_words'].add(first_guess.lower())
                await self.client.send_message(chat_id, first_guess)
                logger.info(f"Started new game in chat {chat_id} with word: {first_guess}")
            return

        # Check for Wordle result pattern
        if self.parse_wordle_result(message_text):
            logger.info(f"Got Wordle result in chat {chat_id}")
            clues = self.extract_clues_from_message(message_text)
            if clues:
                game_state['clues'].extend(clues)
                logger.info(f"Updated clues for chat {chat_id}: {game_state['clues']}")

            # Add realistic delay before next guess (thinking time)
            await asyncio.sleep(random.uniform(3, 8))

            # Send typing action to show we're thinking
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(2, 4))

            # Get next best guess using advanced analysis
            used_words = game_state.get('used_words', set())
            next_guess = self.get_best_guess(game_state['clues'], used_words)
            if next_guess and next_guess.lower() not in used_words:
                game_state.setdefault('used_words', set()).add(next_guess.lower())
                logger.info(f"Next guess for chat {chat_id}: {next_guess}")
                await self.client.send_message(chat_id, next_guess)
            else:
                logger.warning(f"Could not generate new guess for chat {chat_id}")

    async def get_groups(self):
        """Get list of groups the userbot is in"""
        try:
            groups = []
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    groups.append({
                        'id': dialog.id,
                        'title': dialog.title
                    })
            return groups
        except Exception as e:
            logger.error(f"Error getting groups: {e}")
            return []

    async def start_game_in_group(self, chat_id):
        """Start a Wordle game in the specified group"""
        try:
            # Initialize game state with empty used words set
            self.active_games[chat_id] = {
                'clues': [],
                'used_words': set(),
                'active': True
            }

            # Add realistic delay before starting
            await asyncio.sleep(random.uniform(2, 4))

            # Send typing action to appear like a real user
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(random.uniform(1, 2))

            # Send first guess - use a strategic starting word
            first_guess = self.get_best_guess([], set())
            if first_guess:
                self.active_games[chat_id]['used_words'].add(first_guess.lower())
                await self.client.send_message(chat_id, first_guess)
                logger.info(f"Started game in chat {chat_id} with word: {first_guess}")

        except Exception as e:
            logger.error(f"Error starting game in chat {chat_id}: {e}")
            raise

    async def stop_all_games(self):
        """Stop all active games"""
        self.active_games.clear()
        logger.info("Stopped all active games")

    async def stop(self):
        """Stop the userbot"""
        if self.client:
            await self.stop_all_games()
            await self.client.disconnect()
            logger.info("Userbot stopped")

async def start_userbot():
    """Start the userbot"""
    global _userbot_instance

    try:
        # Get environment variables
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        session_string = os.getenv('SESSION_STRING')

        if not all([api_id, api_hash, session_string]):
            logger.error("Missing required environment variables")
            return None

        # Create and start userbot
        userbot = WordleUserBot(int(api_id), api_hash, session_string)
        await userbot.start()

        _userbot_instance = userbot
        return userbot

    except Exception as e:
        logger.error(f"Failed to start userbot: {e}")
        return None

async def stop_userbot():
    """Stop the userbot"""
    global _userbot_instance

    if _userbot_instance:
        await _userbot_instance.stop()
        _userbot_instance = None

def get_userbot():
    """Get the current userbot instance"""
    return _userbot_instance
