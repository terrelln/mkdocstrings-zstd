#ifndef FILE1_H
#define FILE1_H

/**
 * A macro that forwards its argument.
 *
 * @param x an integer to forward
 * @returns @p x
 */
#define MACRO1(x) x

typedef struct struct1_s struct1;

/**
 * A function that does something with @p s and @p x.
 *
 * @pre `s != NULL`
 * @pre `x > 0`
 * @post `s->x == x`
 * @param s a struct to operate on with type @ref struct1
 * @param x an integer to operate on
 * @return `s->x`
 */
int func1(struct1* s, int x);

typedef enum {
    /// The first enum value
    enum1_value1 = 0,
    /**
     * Another enum value that uses a macro @ref MACRO1
     */
    MACRO1(enum1_value2),
    enum1_value3, //< third enum value
    enum1_value5 = 5, //< explicit initializer
} enum1;

struct s1 {
    int x;
    enum1 e;
    int y;
};

union u1 {
    int x;
    s1 s;
};

/**
 * @defgroup g1 Group 1
 */

/**
 * @ingroup g1
 */
const int x = 0;

/**
 * @ingroup g1
 */
#define G1_MACRO 5

/**
 * @ingroup g1
 */
enum g1_enum {
    G1_ENUM_VALUE1,
};

/**
 * @ingroup g1
 */
struct g1_struct {
    int x;
};

/**
 * @ingroup g1
 */
union g1_union {
    struct g1_struct s;
};

/**
 * @ingroup g1
 */
struct g1_struct g1_func(g1_enum e);

/**
 * This is some inline documentation that goes straight
 * into a return without a newline.
 * @returns Something
 *          with a multiline
 * @note This is an important note
 * @warning Followed by a very important warning
 *
 * Finally some text
 * @param x This is a param
 * @param[out] y This is another param
 *
 * @param z Finally a 3rd param
 *
 * Followed by some more text
 */
int func_in_para_returns(int x);

/**
 * text
 * - item1
 * - item2
 *
 * more
 *
 * - item1
 */
int var_list_items;

/// brief description
int var_brief;

/**
 * @brief brief description
 *
 * Followed by a longer description
 */
int var_brief_and_detailed;

/**
 * Test markups like **bold** and *italics*
 * work as expected.
 */
int var_markups;

#endif