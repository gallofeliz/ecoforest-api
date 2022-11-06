# ecoforest-api

See docker-compose.yml ; option ECOFOREST_USERNAME/PASSWORD if proxy (without auth) is used

Call /summary and have

```
{
    temperature: 19.1,
    power: 5,
    status: 7,
    humanStatus: 'running',
    mode: 'power',
    targetPower: 5
}
```

Others endpoints are available to control the stove.

## Super mode

Call /super-mode with :
- softest/soft/soft1/soft2/soft3 : power 1, 2, 3 with slow convection -> silence !
- mid/mid1/mid2/mid3  : power 4, 5, 6 with normal convection
- hard/hardest/hard1/hard2/hard3 : power 7, 8, 9 with fast convection -> Warm fast !!
