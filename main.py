import pandas as pd
import itertools
from tqdm import tqdm
from ruaccent import RUAccent
import language_tool_python

accentizer = RUAccent()
accentizer.load(omograph_model_size='turbo3', tiny_mode=False)

tool = language_tool_python.LanguageTool('ru-RU')

pron_dict = pd.read_csv('russian_mfa.tsv', sep='\t')    # считываем файла с транскрипциями
pron_dict = pron_dict.drop([0, 1, 2])   # удаляем лишние элементы
pron_dict.rename(columns={'<cutoff>': 'word', 'spn': 'transcription'}, inplace=True)    # добавляем названия столбцов
# получаем список всех фонем, использующихся в транскрипиях
phonemes = set(' '.join(pron_dict['transcription'].to_list()).split())
# вручную выбираем гласные
vowels = {'a', 'e', 'i', 'o', 'u', 'æ', 'ɐ', 'ə', 'ɛ', 'ɨ', 'ɪ', 'ɵ', 'ʉ', 'ʊ'}
# получаем согласные, вычитая из множества фонем множество гласных, превращаем в строку для регулярного выражения
consonants = ''.join(list(phonemes - vowels))


def generate_combinations(lst) -> list:
    result = []

    # Функция для превращения вложенных списков в их элементы
    def unravel(lst):
        if isinstance(lst, list):  # если элемент - это список
            return [unravel(item) for item in lst]  # рекурсивно разворачиваем его
        else:
            return lst  # если элемент не список, возвращаем его

    # Распаковываем вложенные списки
    unpacked = [unravel(x) if isinstance(x, list) else [x] for x in lst]

    # Получаем декартово произведение
    for combination in itertools.product(*unpacked):
        result.append(list(combination))

    return result


def get_pronunciation(phrase: str) -> list:
    pronunciations = []
    for word in phrase.split():
        found = pron_dict[pron_dict['word'].str.lower() == word.lower()]['transcription'].to_list()
        if found:
            pronunciations.append(found)
        else:
            pronunciations.append(0)
    return generate_combinations(pronunciations)


def get_vowels_masks(phrase: str) -> list:
    vowels_masks = []
    for variant in get_pronunciation(phrase):
        variant_vowels_masks = ''
        for word in variant:
            if word != 0:
                mask = ''
                for phoneme in word.split():
                    if phoneme in vowels:
                        mask += phoneme + ' '
                    else:
                        mask += f'([{consonants}][ʲː̪]?[ː]?\s?)? '
                variant_vowels_masks += mask
            else:
                variant_vowels_masks += '.*'
        vowels_masks.append(variant_vowels_masks)
    return vowels_masks


def generate_partitions(s: str):
    s = get_vowels_masks(s)[0].split()

    def backtrack(start):
        if start == len(s):
            yield []
            return

        for end in range(start + 1, len(s) + 1):
            if not pron_dict[pron_dict.transcription.str.fullmatch(' '.join(s[start:end]))].empty and len(
                    s[start:end]) > 3:
                for partition in backtrack(end):
                    yield [s[start:end]] + partition

    return backtrack(0)


def get_words_by_mask(mask: list) -> list:
    l = []
    l += pron_dict[pron_dict.transcription.str.fullmatch(' '.join(mask))]['word'].to_list()
    return l


def get_accents(phrase):
    accents = accentizer.process_all(phrase)
    vowels = 'аеёиоуыэюя'
    result = ''
    for letter in accents:
        if letter in vowels:
            result += 'V'
        elif letter == '+':
            result += '+'
    return result


def get_similar(phrase):
    partition = list(generate_partitions(phrase))
    result = []
    phrase_accent = get_accents(phrase)
    for phon_phrase in tqdm(partition):
        words = []
        for mask in phon_phrase:
            words.append(get_words_by_mask(mask))
        result.extend(generate_combinations(words))
    for i in tqdm(range(len(result))):
        result[i] = ' '.join(result[i])
        print(result[i])
    correct = [r for r in tqdm(result) if not tool.check(r.upper()) and phrase_accent == get_accents(r)]
    return correct


if __name__ == '__main__':
    print('Введите фразу: ')
    print(get_similar(input()))
