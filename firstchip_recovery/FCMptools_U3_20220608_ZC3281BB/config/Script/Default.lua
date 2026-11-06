--¶«ÁÕ

HexMode = 0 -- 0 Text mode, 1 Hex mode, global

local btnew = ByteArray.btnew
local btget = ByteArray.btget
local btset = ByteArray.btset
local bttostring = ByteArray.bttostring
local bttoarray = ByteArray.bttoarray
local btarraycopy = ByteArray.btarraycopy
local btmemcmp = ByteArray.btmemcmp
local btmemset = ByteArray.btmemset

local DeviceCount

local ErrTable = {
	{0x20, "0060"}, --ºìÂÌµÆ
	{0x21, "0033"},
	
	{0x61, "0061"},--Normal Bin
	{0x62, "0062"},
	{0x63, "0063"},
	{0x64, "0064"},
	{0x65, "0065"},
	{0x66, "0066"},
	{0x67, "0067"},
	{0x68, "0068"},
	{0x69, "0069"},
	{0x11, "0051"},--Bin 1B

	{0x30, "0030"},--To many bad blocks
	{0x31, "0071"},--ReID Bin
	{0x32, "0072"},
	{0x33, "0073"},
	{0x34, "0074"},
	{0x35, "0075"},
	{0x36, "0076"},
	{0x37, "0077"},
	{0x38, "0078"},
	{0x39, "0079"},
	
	{0x81, "0036"}, --open file fail
	{0x82, "0032"}, --CMD Time out
	{0x83, "0030"}, --To many bad blocks
	{0x84, "0037"}, --read table fail
	{0x85, "0038"}, --check table data fail
	{0x86, "0039"}, --format fail
	{0x87, "0033"}, --Unknown Flash
	{0x88, "0002"}, --user abort
	{0x89, "0030"}, --Unknown error
	{0x8a, "003a"}, --Flash Write Protected
	{0x8b, "003b"}, --Program exception
	{0x8c, "003c"}, --Program version incorrect
	{0x8D, "0031"}, --RB Abnormal
	{0x8E, "003d"}, --bad ic
	{0x8f, "003e"}, --ic not match
	{0x90, "003f"}, --boot fail
	{0x91, "0040"}, --read efuse fail
	{0x92, "0041"}, --efuse already exist
	{0x93, "0042"}, --read e2proom fail
	{0x94, "0032"}, --Sort Time out
	{0x95, "ffff"}, --adddisk timeout
	{0x96, "0035"}, --No Flash
	{0x97, "0255"}, --No Test
	{0x98, "0044"}, --device lost
	{0x99, "0045"}, --decode fail
	
	{0x9D, "009d"}, --dqsdelay fail
}

function RecvMessage(command, contype)
	local startStr = ""
	if contype == 1 then --COM mode @START_TEST 00
		startStr = "@START_TEST 00 "
	elseif contype == 2 then  --TCP/IP @START_TEST
		startStr = "@START_TEST "
	else
		return false
	end

	local pos = string.find(command, startStr)
	if pos == nil or pos ~= 1 then
		return false
	end

	if string.sub(command, string.len(command)) ~= "+" then
		return false
	end

	command = string.gsub(command, startStr, "")
	command = string.gsub(command, " ", "")
	command = string.gsub(command, "+", "")

	DeviceCount = string.len(command)


	local result = btnew(DeviceCount, 0)
	for i = 0, DeviceCount - 1 do
		if string.sub(command, i + 1, i + 1) == "1" then
			btset(result, i, 1)
		else
			btset(result, i, 0)
		end
	end

	return true, DeviceCount, result
end

function AnswerControler(buf, len, contype)
	local result = ""
	if contype == 1 then --COM mode @START_TEST 00
		result = result .. "@TEST_DONE 00"
	elseif contype == 2 then  --TCP/IP @START_TEST
		result = result .. "@TEST_DONE"
	else
		return 0
	end

	for i = 0, len - 1 do
		result = result.." "..GetCode(btget(buf, i))
		--[[
		if (btget(buf, i) & 0x80) == 0 then
			result = result .. " 0001"
		else
			result = result .. " 0000"
		end
		]]
	end

	result = result .. "+"
	return 1, result
end

function TimeOut(contype)
	return "@TIMEOUT+"
end

function GetCode(bt)
	for i = 1, #ErrTable do
		if ErrTable[i][1] == bt then
			return ErrTable[i][2]
		end
	end

	if (bt & 0x80) == 0 then
		return "0001"
	else
		return "0000"
	end

	return "XXXX" --Unknown Error
end

function ConfigPath()
	return "D:\\IP\\DGHandlerIP.ini"
end

function IsAutoDownload(command)
	local startStr = "@AUTO_DOWNLOAD "

	local pos = string.find(command, startStr)
	if pos == nil or pos ~= 1 then
		return false
	end

	if string.sub(command, string.len(command)) ~= "+" then
		return false
	end

	command = string.gsub(command, startStr, "")
	command = string.gsub(command, " ", "")
	command = string.gsub(command, "+", "")

	return true, command
end

function AutoDownload(state)
	if state > 0 then
		return "@AUTO_DOWNLOAD OK+"
	else
		return "@AUTO_DOWNLOAD FAIL+"
	end
end

