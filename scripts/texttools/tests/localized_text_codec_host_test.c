#include "global.h"

#include <stdio.h>
#include <string.h>

#include "localized_text_codec.h"
#include "localized_text_codec_host_fixture.h"

#define ARRAY_COUNT(array) (sizeof(array) / sizeof((array)[0]))
#define GUARD_VALUE 0xA5

static int CheckGuards(const u8 *storage, u32 outputCapacity)
{
    if (storage[0] != GUARD_VALUE)
        return 0;
    if (storage[outputCapacity + 1] != GUARD_VALUE)
        return 0;
    return 1;
}

static int TestCorpus(void)
{
    u8 storage[HOST_FIXTURE_EXPECTED_SIZE + 2];
    u32 decodedLength;
    enum LocalizedTextCodecStatus status;

    memset(storage, GUARD_VALUE, sizeof(storage));
    status = LocalizedTextCodec_Decode(
        gHostFixtureNodes,
        ARRAY_COUNT(gHostFixtureNodes),
        HOST_FIXTURE_ROOT_INDEX,
        gHostFixtureCompressed,
        ARRAY_COUNT(gHostFixtureCompressed),
        storage + 1,
        HOST_FIXTURE_EXPECTED_SIZE,
        &decodedLength);

    if (status != LOCALIZED_TEXT_CODEC_OK)
        return 0;
    if (decodedLength != HOST_FIXTURE_EXPECTED_SIZE)
        return 0;
    if (memcmp(storage + 1, gHostFixtureExpected, HOST_FIXTURE_EXPECTED_SIZE) != 0)
        return 0;
    return CheckGuards(storage, HOST_FIXTURE_EXPECTED_SIZE);
}

static int TestMalformedChild(void)
{
    static const u32 nodes[] = {0x00020002, 0xFFFF0000};
    static const u8 input[] = {0};
    u8 storage[4];
    u32 decodedLength;
    enum LocalizedTextCodecStatus status;

    memset(storage, GUARD_VALUE, sizeof(storage));
    status = LocalizedTextCodec_Decode(
        nodes, ARRAY_COUNT(nodes), 0, input, ARRAY_COUNT(input),
        storage + 1, 2, &decodedLength);

    return status == LOCALIZED_TEXT_CODEC_INVALID_NODE
        && decodedLength == 0
        && CheckGuards(storage, 2);
}

static int TestTruncatedInput(void)
{
    static const u32 nodes[] = {
        0x00090001, 0x00090002, 0x00090003, 0x00090004, 0x00090005,
        0x00090006, 0x00090007, 0x00090008, 0x00090009, 0xFFFF0000
    };
    static const u8 input[] = {0};
    u8 storage[4];
    u32 decodedLength;
    enum LocalizedTextCodecStatus status;

    memset(storage, GUARD_VALUE, sizeof(storage));
    status = LocalizedTextCodec_Decode(
        nodes, ARRAY_COUNT(nodes), 0, input, ARRAY_COUNT(input),
        storage + 1, 2, &decodedLength);

    return status == LOCALIZED_TEXT_CODEC_TRUNCATED_INPUT
        && decodedLength == 0
        && CheckGuards(storage, 2);
}

static int TestMissingTerminator(void)
{
    static const u32 nodes[] = {0xFFFF0041, 0xFFFF0000, 0x00010000};
    static const u8 input[] = {0};
    u8 storage[10];
    u32 decodedLength;
    enum LocalizedTextCodecStatus status;

    memset(storage, GUARD_VALUE, sizeof(storage));
    status = LocalizedTextCodec_Decode(
        nodes, ARRAY_COUNT(nodes), 2, input, ARRAY_COUNT(input),
        storage + 1, 8, &decodedLength);

    return status == LOCALIZED_TEXT_CODEC_MISSING_TERMINATOR
        && decodedLength == 8
        && CheckGuards(storage, 8);
}

static int TestOutputOverflow(void)
{
    static const u32 nodes[] = {0xFFFF0041, 0xFFFF0000, 0x00010000};
    static const u8 input[] = {2};
    u8 storage[3];
    u32 decodedLength;
    enum LocalizedTextCodecStatus status;

    memset(storage, GUARD_VALUE, sizeof(storage));
    status = LocalizedTextCodec_Decode(
        nodes, ARRAY_COUNT(nodes), 2, input, ARRAY_COUNT(input),
        storage + 1, 1, &decodedLength);

    return status == LOCALIZED_TEXT_CODEC_OUTPUT_OVERFLOW
        && decodedLength == 1
        && storage[1] == 'A'
        && CheckGuards(storage, 1);
}

static int TestInvalidPairedZero(void)
{
    static const u32 nodes[] = {0xFFFF0100, 0xFFFF0000, 0x00010000};
    static const u8 input[] = {0};
    u8 storage[4];
    u32 decodedLength;
    enum LocalizedTextCodecStatus status;

    memset(storage, GUARD_VALUE, sizeof(storage));
    status = LocalizedTextCodec_Decode(
        nodes, ARRAY_COUNT(nodes), 2, input, ARRAY_COUNT(input),
        storage + 1, 2, &decodedLength);

    return status == LOCALIZED_TEXT_CODEC_INVALID_SYMBOL
        && decodedLength == 0
        && CheckGuards(storage, 2);
}

static int TestNodeConvention(void)
{
    u32 leaf;
    u32 internal;

    leaf = 0xFFFF0000u | 0x1234u;
    internal = (0x0022u << 16) | 0x0011u;
    return leaf == 0xFFFF1234u && internal == 0x00220011u;
}

int main(void)
{
    if (!TestCorpus())
        return 1;
    if (!TestMalformedChild())
        return 2;
    if (!TestTruncatedInput())
        return 3;
    if (!TestMissingTerminator())
        return 4;
    if (!TestOutputOverflow())
        return 5;
    if (!TestInvalidPairedZero())
        return 6;
    if (!TestNodeConvention())
        return 7;

    puts("localized_text_codec_host_test: ok");
    return 0;
}
