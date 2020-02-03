/*
*
* countmin.cpp
* Class implementing countmin sketch for reads
*
*/

#include "countmin.hpp"

// C/C++/C++11/C++17 headers
#include <cmath>
#include <iterator>
#include <limits>

#include "countmin.hpp"

const unsigned int table_width_bits = 24;
const unsigned int hash_per_hash = (int)floor(64/table_width_bits);
constexpr uint64_t mask{ 0x4FFFFF }; // 24 lowest bits ON

// Constructors

KmerCounter::KmerCounter(const uint8_t min_count, const size_t num_hashes)
:_min_count(min_count), _num_hashes_needed(num_hashes)
{
}

KmerCounter::~KmerCounter() {};

CountMin::CountMin(const uint8_t min_count)
:KmerCounter(min_count, table_rows/hash_per_hash)
{
    for (auto row_it = hash_table.begin(); row_it != hash_table.end(); row_it++)
    {
        row_it->fill(0);
    }
}

HashCounter::HashCounter(const uint8_t min_count)
:KmerCounter(min_count, 0)
{
}

uint8_t CountMin::add_count(ntHashIterator& hash)
{
    uint8_t min_count = 0;
    for (unsigned int hash_nr = 0; hash_nr < table_rows; hash_nr+=hash_per_hash)
    {
        uint64_t hash_val = (*hash)[hash_nr/hash_per_hash];
        for (unsigned int i = 0; i < hash_per_hash; i++)
        {
            uint32_t hash_val_masked = hash_val & mask;
            if (hash_table[hash_nr + i][hash_val_masked] < std::numeric_limits<uint8_t>::max())
            {
                if (++hash_table[hash_nr + i][hash_val_masked] > min_count)
                {
                    min_count = hash_table[hash_nr + i][hash_val_masked];
                }
            }
            else
            {
                min_count = std::numeric_limits<uint8_t>::max();
                break;
            }
            hash_val = hash_val >> table_width_bits;
        }
    }
    return(min_count);
}

bool KmerCounter::above_min(ntHashIterator& hash)
{
    return (add_count(hash) > _min_count);
}

uint8_t HashCounter::add_count(ntHashIterator& hash)
{
    uint8_t count = 0;
    auto table_val = hash_table.find((*hash)[0]);
    if (table_val == hash_table.end())
    {
        hash_table[(*hash)[0]] = 1;
        count = 1;
    }
    else if (table_val->second < std::numeric_limits<uint8_t>::max())
    {
        (table_val->second)++;
        count = table_val->second; 
    }
    return(count);
}

uint8_t HashCounter::probe(ntHashIterator& hash)
{
    return(hash_table[(*hash)[0]]);
}
