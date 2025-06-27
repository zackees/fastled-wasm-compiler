#include <FastLED.h>

#include "fl/audio.h"
#include "fl/math.h"
#include "lib/file.h"

UIAudio audio("Audio");
TestClass testObj;

void setup() {
    testObj.doSomething();
    testFunction();
}

void loop()
{

    while (AudioSample sample = audio.next())
    {
        for (int i = 0; i < sample.pcm().size(); ++i)
        {
            int32_t x = ABS(sample.pcm()[i]);
            if (x > max)
            {
                max = x;
            }
        }
    }
}