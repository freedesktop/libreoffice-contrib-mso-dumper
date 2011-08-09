########################################################################
#
#  Copyright (c) 2010 Kohei Yoshida
#  
#  Permission is hereby granted, free of charge, to any person
#  obtaining a copy of this software and associated documentation
#  files (the "Software"), to deal in the Software without
#  restriction, including without limitation the rights to use,
#  copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following
#  conditions:
#  
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#  
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#  OTHER DEALINGS IN THE SOFTWARE.
#
########################################################################

import struct, sys
import globals, formula, xlsmodel, msodraw

from globals import debug

class RecordError(Exception): pass

# -------------------------------------------------------------------
# record handler classes

class RefU(object):

    def __init__ (self, strm):
        self.row1 = strm.readUnsignedInt(2)
        self.row2 = strm.readUnsignedInt(2)
        self.col1 = strm.readUnsignedInt(1)
        self.col2 = strm.readUnsignedInt(1)

    def toString (self):
        rge = formula.CellRange()
        rge.firstRow = self.row1
        rge.firstCol = self.col1
        rge.lastRow = self.row2
        rge.lastCol = self.col2
        return rge.toString()


class Ref8U(object):

    def __init__ (self, strm):
        self.row1 = strm.readUnsignedInt(2)
        self.row2 = strm.readUnsignedInt(2)
        self.col1 = strm.readUnsignedInt(2)
        self.col2 = strm.readUnsignedInt(2)


class RKAuxData(object):
    """Store auxiliary data for RK value"""
    def __init__ (self):
        self.multi100 = False
        self.signedInt = False

def decodeRK (rkval, auxData = None):
    multi100  = ((rkval & 0x00000001) != 0)
    signedInt = ((rkval & 0x00000002) != 0)
    realVal   = (rkval & 0xFFFFFFFC)

    if signedInt:
        # for integer, perform right-shift by 2 bits.
        realVal = realVal/4
    else:
        # for floating-point, convert the value back to the bytes,
        # pad the bytes to make it 8-byte long, and convert it back
        # to the numeric value.
        tmpBytes = struct.pack('<L', realVal)
        tmpBytes = struct.pack('xxxx') + tmpBytes
        realVal = struct.unpack('<d', tmpBytes)[0]

    if multi100:
        realVal /= 100.0

    if auxData != None:
        auxData.multi100 = multi100
        auxData.signedInt = signedInt

    return realVal

class LongRGB(object):
    def __init__ (self, r, g, b):
        self.red = r
        self.green = g
        self.blue = b

class ICV(object):
    def __init__ (self, value):
        self.value = value

    def toString (self):
        return "color=0x%2.2X"%self.value

class BaseRecordHandler(globals.ByteStream):

    def __init__ (self, header, size, bytes, strmData):
        globals.ByteStream.__init__(self, bytes)
        self.header = header
        self.lines = []
        self.strmData = strmData

    def parseBytes (self):
        """Parse the original bytes and generate human readable output.

The derived class should only worry about overwriting this function.  The
bytes are given as self.bytes, and call self.appendLine([new line]) to
append a line to be displayed.
"""
        pass

    def fillModel (self, model):
        """Parse the original bytes and populate the workbook model.

Like parseBytes(), the derived classes must overwrite this method."""
        pass

    def __getHeaderStr (self):
        return "%4.4Xh: "%self.header

    def output (self):
        headerStr = self.__getHeaderStr()
        print (headerStr + "-"*(globals.OutputWidth-len(headerStr)))
        try:
            self.parseBytes()
            for line in self.lines:
                print (headerStr + line)
        except:
            print(headerStr + "Error interpreting the record!")

    def debug (self, msg):
        print ("%4.4Xh: %s"%(self.header, msg))

    def appendLine (self, line):
        self.lines.append(line)

    def appendMultiLine (self, line):
        charWidth = globals.OutputWidth - len(self.__getHeaderStr())
        singleLine = ''
        testLine = ''
        for word in line.split():
            testLine += word + ' '
            if len(testLine) > charWidth:
                self.lines.append(singleLine)
                testLine = word + ' '
            singleLine = testLine

        if len(singleLine) > 0:
            self.lines.append(singleLine)

    def appendLineBoolean (self, name, value):
        text = "%s: %s"%(name, self.getYesNo(value))
        self.appendLine(text)

    def appendCellPosition (self, col, row):
        text = "cell position: (col: %d; row: %d)"%(col, row)
        self.appendLine(text)

    def getYesNo (self, boolVal):
        if boolVal:
            return 'yes'
        else:
            return 'no'

    def getTrueFalse (self, boolVal):
        if boolVal:
            return 'true'
        else:
            return 'false'

    def getEnabledDisabled (self, boolVal):
        if boolVal:
            return 'enabled'
        else:
            return 'disabled'

    def getBoolVal (self, boolVal, trueStr, falseStr):
        if boolVal:
            return trueStr
        else:
            return falseStr

    def readShortXLUnicodeString (self):
        cch = self.readUnsignedInt(1)
        return self.readUnicodeString(cch)

    def readLongRGB (self):
        r = self.readUnsignedInt(1)
        g = self.readUnsignedInt(1)
        b = self.readUnsignedInt(1)
        self.readBytes(1) # reserved
        return LongRGB(r, g, b)

    def readICV (self):
        return ICV(self.readUnsignedInt(2))

class AutofilterInfo(BaseRecordHandler):

    def __parseBytes (self):
        self.arrowCount = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("number of autofilter arrows: %d"%self.arrowCount)

    def fillModel (self, model):
        self.__parseBytes()
        sh = model.getCurrentSheet()
        sh.setAutoFilterArrowSize(self.arrowCount)



class Autofilter(BaseRecordHandler):

    class DoperType:
        FilterNotUsed     = 0x00  # filter condition not used
        RKNumber          = 0x02
        Number            = 0x04  # IEEE floating point nubmer
        String            = 0x06
        BooleanOrError    = 0x08
        MatchAllBlanks    = 0x0C
        MatchAllNonBlanks = 0x0E

    compareCodes = [
        '< ', # 01
        '= ', # 02
        '<=', # 03
        '> ', # 04
        '<>', # 05
        '>='  # 06
    ]

    errorCodes = {
        0x00: '#NULL! ',
        0x07: '#DIV/0!', 
        0x0F: '#VALUE!', 
        0x17: '#REF!  ', 
        0x1D: '#NAME? ', 
        0x24: '#NUM!  ', 
        0x2A: '#N/A   '
    }

    class Doper(object):
        def __init__ (self, dataType=None):
            self.dataType = dataType
            self.sign = None

        def appendLines (self, hdl):
            # data type
            s = '(unknown)'
            if self.dataType == Autofilter.DoperType.RKNumber:
                s = "RK number"
            elif self.dataType == Autofilter.DoperType.Number:
                s = "number"
            elif self.dataType == Autofilter.DoperType.String:
                s = "string"
            elif self.dataType == Autofilter.DoperType.BooleanOrError:
                s = "boolean or error"
            elif self.dataType == Autofilter.DoperType.MatchAllBlanks:
                s = "match all blanks"
            elif self.dataType == Autofilter.DoperType.MatchAllNonBlanks:
                s = "match all non-blanks"
            hdl.appendLine("  data type: %s"%s)

            # comparison code
            if self.sign != None:
                s = globals.getValueOrUnknown(Autofilter.compareCodes, self.sign)
                hdl.appendLine("  comparison code: %s (%d)"%(s, self.sign))


    class DoperRK(Doper):
        def __init__ (self):
            Autofilter.Doper.__init__(self, Autofilter.DoperType.RK)
            self.rkval = None

        def appendLines (self, hdl):
            Autofilter.Doper.appendLines(self, hdl)
            hdl.appendLine("  value: %g"%decodeRK(self.rkval))

    class DoperNumber(Doper):
        def __init__ (self):
            Autofilter.Doper.__init__(self, Autofilter.DoperType.Number)
            self.number = None

        def appendLines (self, hdl):
            Autofilter.Doper.appendLines(self, hdl)
            hdl.appendLine("  value: %g"%self.number)

    class DoperString(Doper):
        def __init__ (self):
            Autofilter.Doper.__init__(self, Autofilter.DoperType.String)
            self.strLen = None

        def appendLines (self, hdl):
            Autofilter.Doper.appendLines(self, hdl)
            if self.strLen != None:
                hdl.appendLine("  string length: %d"%self.strLen)


    class DoperBoolean(Doper):
        def __init__ (self):
            Autofilter.Doper.__init__(self, Autofilter.DoperType.Boolean)
            self.flag = None
            self.value = None

        def appendLines (self, hdl):
            Autofilter.Doper.appendLines(self, hdl)
            hdl.appendLine("  boolean or error: %s"%hdl.getBoolVal(self.flag, "error", "boolean"))
            if self.flag:
                # error value
                hdl.appendLine("  error value: %s (0x%2.2X)"%
                    (globals.getValueOrUnknown(Autofilter.errorCodes, self.value), self.value))
            else:
                # boolean value
                hd.appendLine("  boolean value: %s"%hdl.getTrueFalse(self.value))


    def __readDoper (self):
        vt = self.readUnsignedInt(1)
        if vt == Autofilter.DoperType.RKNumber:
            doper = Autofilter.DoperRK()
            doper.sign = self.readUnsignedInt(1)
            doper.rkval = self.readUnsignedInt(4)
            self.readBytes(4) # ignore 4 bytes
        elif vt == Autofilter.DoperType.Number:
            doper = Autofilter.DoperNumber()
            doper.sign = self.readUnsignedInt(1)
            doper.number = self.readDouble()
        elif vt == Autofilter.DoperType.String:
            doper = Autofilter.DoperString()
            doper.sign = self.readUnsignedInt(1)
            self.readBytes(4) # ignore 4 bytes
            doper.strLen = self.readUnsignedInt(1)
            self.readBytes(3) # ignore 3 bytes
        elif vt == Autofilter.DoperType.BooleanOrError:
            doper = Autofilter.DoperBoolean()
            doper.sign = self.readUnsignedInt(1)
            doper.flag = self.readUnsignedInt(1)
            doper.value = self.readUnsignedInt(1)
            self.readBytes(6) # ignore 6 bytes
        else:
            doper = Autofilter.Doper()
            self.readBytes(10) # ignore the entire 10 bytes
        return doper

    def __parseBytes (self):
        self.filterIndex = self.readUnsignedInt(2)  # column ID?
        flag = self.readUnsignedInt(2)
        self.join    = (flag & 0x0003) # 1 = ANDed  0 = ORed
        self.simple1 = (flag & 0x0004) # 1st condition is simple equality (for optimization)
        self.simple2 = (flag & 0x0008) # 2nd condition is simple equality (for optimization)
        self.top10   = (flag & 0x0010) # top 10 autofilter
        self.top     = (flag & 0x0020) # 1 = top 10 filter shows the top item, 0 = shows the bottom item
        self.percent = (flag & 0x0040) # 1 = top 10 shows percentage, 0 = shows items
        self.itemCount = (flag & 0xFF80) / (2*7)
        self.doper1 = self.__readDoper()
        self.doper2 = self.__readDoper()

        # pick up string(s)
        self.string1 = None
        if self.doper1.dataType == Autofilter.DoperType.String:
            self.string1 = globals.getTextBytes(self.readBytes(self.doper1.strLen))

        self.string2 = None
        if self.doper2.dataType == Autofilter.DoperType.String:
            self.string2 = globals.getTextBytes(self.readBytes(self.doper2.strLen))

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("filter index (= column ID): %d"%self.filterIndex)
        self.appendLine("joining: %s"%self.getBoolVal(self.join, "AND", "OR"))
        self.appendLineBoolean("1st condition is simple equality", self.simple1)
        self.appendLineBoolean("2nd condition is simple equality", self.simple2)
        self.appendLineBoolean("top 10 autofilter", self.top10)
        if self.top10:
            self.appendLine("top 10 shows: %s"%self.getBoolVal(self.top, "top item", "bottom item"))
            self.appendLine("top 10 shows: %s"%self.getBoolVal(self.percent, "percentage", "items"))
            self.appendLine("top 10 item count: %d"%self.itemCount)

        self.appendLine("1st condition:")
        self.doper1.appendLines(self)
        self.appendLine("2nd condition:")
        self.doper2.appendLines(self)

        if self.string1 != None:
            self.appendLine("string for 1st condition: %s"%self.string1)

        if self.string2 != None:
            self.appendLine("string for 2nd condition: %s"%self.string2)

    def fillModel (self, model):
        self.__parseBytes()
        sh = model.getCurrentSheet()
        obj = xlsmodel.AutoFilterArrow(self.filterIndex)
        obj.isActive = True
        obj.equalString1 = self.string1
        obj.equalString2 = self.string2
        sh.setAutoFilterArrow(self.filterIndex, obj)
        # TODO: Pick up more complex states as we need them.


class BOF(BaseRecordHandler):

    Type = {
        0x0005: "Workbook globals",
        0x0006: "Visual Basic module",
        0x0010: "Worksheet or dialog sheet",
        0x0020: "Chart",
        0x0040: "Excel 4.0 macro sheet",
        0x0100: "Workspace file"
    }

    # TODO: Add more build identifiers.
    buildId = {
        0x0DBB: 'Excel 97',
        0x0EDE: 'Excel 97',
        0x2775: 'Excel XP'
    }

    def getBuildIdName (self, value):
        if BOF.buildId.has_key(value):
            return BOF.buildId[value]
        else:
            return '(unknown)'

    def parseBytes (self):
        # BIFF version
        ver = self.readUnsignedInt(2)
        s = 'not BIFF8'
        if ver == 0x0600:
            s = 'BIFF8'
        self.appendLine("BIFF version: %s"%s)

        # Substream type
        dataType = self.readUnsignedInt(2)
        self.appendLine("type: %s"%BOF.Type[dataType])

        # build ID and year
        buildID = self.readUnsignedInt(2)
        self.appendLine("build ID: %s (%4.4Xh)"%(self.getBuildIdName(buildID), buildID))
        buildYear = self.readUnsignedInt(2)
        self.appendLine("build year: %d"%buildYear)

        # file history flags
        flags = self.readUnsignedInt(4)
        win     = (flags & 0x00000001)
        risc    = (flags & 0x00000002)
        beta    = (flags & 0x00000004)
        winAny  = (flags & 0x00000008)
        macAny  = (flags & 0x00000010)
        betaAny = (flags & 0x00000020)
        riscAny = (flags & 0x00000100)
        self.appendLine("last edited by Excel on Windows: %s"%self.getYesNo(win))
        self.appendLine("last edited by Excel on RISC: %s"%self.getYesNo(risc))
        self.appendLine("last edited by beta version of Excel: %s"%self.getYesNo(beta))
        self.appendLine("has ever been edited by Excel for Windows: %s"%self.getYesNo(winAny))
        self.appendLine("has ever been edited by Excel for Macintosh: %s"%self.getYesNo(macAny))
        self.appendLine("has ever been edited by beta version of Excel: %s"%self.getYesNo(betaAny))
        self.appendLine("has ever been edited by Excel on RISC: %s"%self.getYesNo(riscAny))

        lowestExcelVer = self.readSignedInt(4)
        self.appendLine("earliest Excel version that can read all records: %d"%lowestExcelVer)

    def fillModel (self, model):
        if model.modelType != xlsmodel.ModelType.Workbook:
            return

        sheet = model.appendSheet()
        ver = self.readUnsignedInt(2)
        s = 'not BIFF8'
        if ver == 0x0600:
            s = 'BIFF8'
        sheet.version = s



class BoundSheet(BaseRecordHandler):

    hiddenStates = {0x00: 'visible', 0x01: 'hidden', 0x02: 'very hidden'}

    sheetTypes = {0x00: 'worksheet or dialog sheet',
                  0x01: 'Excel 4.0 macro sheet',
                  0x02: 'chart',
                  0x06: 'Visual Basic module'}

    @staticmethod
    def getHiddenState (flag):
        if BoundSheet.hiddenStates.has_key(flag):
            return BoundSheet.hiddenStates[flag]
        else:
            return 'unknown'

    @staticmethod
    def getSheetType (flag):
        if BoundSheet.sheetTypes.has_key(flag):
            return BoundSheet.sheetTypes[flag]
        else:
            return 'unknown'

    def __parseBytes (self):
        self.posBOF = self.readUnsignedInt(4)
        flags = self.readUnsignedInt(2)
        textLen = self.readUnsignedInt(1)
        self.name, textLen = globals.getRichText(self.readRemainingBytes(), textLen)
        self.hiddenState = (flags & 0x0003)
        self.sheetType = (flags & 0xFF00)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("BOF position in this stream: %d"%self.posBOF)
        self.appendLine("sheet name: %s"%self.name)
        self.appendLine("hidden state: %s"%BoundSheet.getHiddenState(self.hiddenState))
        self.appendLine("sheet type: %s"%BoundSheet.getSheetType(self.sheetType))

    def fillModel (self, model):
        self.__parseBytes()
        wbglobal = model.getWorkbookGlobal()
        data = xlsmodel.WorkbookGlobal.SheetData()
        data.name = self.name
        data.visible = not self.hiddenState
        wbglobal.appendSheetData(data)


class CF(BaseRecordHandler):

    def __parseBytes (self):
        self.conditionType = self.readUnsignedInt(1)
        self.compFunction = self.readUnsignedInt(1)
        sizeFormula1 = self.readUnsignedInt(2)
        sizeFormula2 = self.readUnsignedInt(2)
        self.__parseDXFN()

        self.formula1 = self.readBytes(sizeFormula1)
        self.formula2 = self.readBytes(sizeFormula2)

    def __parseDXFN (self):

        bits = self.readUnsignedInt(4)
        self.alchNinch          = (bits & 0x00000001) != 0  # whether the value of dxfalc.alc MUST be ignored.
        self.alcvNinch          = (bits & 0x00000002) != 0  # whether the value of dxfalc.alcv MUST be ignored.
        self.wrapNinch          = (bits & 0x00000004) != 0  # whether the value of dxfalc.fWrap MUST be ignored.
        self.trotNinch          = (bits & 0x00000008) != 0  # whether the value of dxfalc.trot MUST be ignored.
        self.kintoNinch         = (bits & 0x00000010) != 0  # whether the value of dxfalc.fJustLast MUST be ignored.
        self.cIndentNinch       = (bits & 0x00000020) != 0  # whether the values of dxfalc.cIndent and dxfalc.iIndent MUST be ignored.
        self.fShrinkNinch       = (bits & 0x00000040) != 0  # whether the value of dxfalc.fShrinkToFit MUST be ignored.
        self.fMergeCellNinch    = (bits & 0x00000080) != 0  # whether the value of dxfalc.fMergeCell MUST be ignored.
        self.lockedNinch        = (bits & 0x00000100) != 0  # whether the value of dxfprot.fLocked MUST be ignored.
        self.hiddenNinch        = (bits & 0x00000200) != 0  # whether the value of dxfprot.fHidden MUST be ignored.
        self.glLeftNinch        = (bits & 0x00000400) != 0  # whether the values of dxfbdr.dgLeft and dxfbdr.icvLeft MUST be ignored .
        self.glRightNinch       = (bits & 0x00000800) != 0  # whether the values of dxfbdr.dgRight and dxfbdr.icvRight MUST be ignored.
        self.glTopNinch         = (bits & 0x00001000) != 0  # whether the values of dxfbdr.dgTop and dxfbdr.icvTop MUST be ignored.
        self.glBottomNinch      = (bits & 0x00002000) != 0  # whether the values of dxfbdr.dgBottom and dxfbdr.icvBottom MUST be ignored.
        self.glDiagDownNinch    = (bits & 0x00004000) != 0  # whether the value of dxfbdr.bitDiagDown MUST be ignored.
        self.glDiagUpNinch      = (bits & 0x00008000) != 0  # whether the value of dxfbdr.bitDiagUp MUST be ignored.
        self.flsNinch           = (bits & 0x00010000) != 0  # whether the value of dxfpat.fls MUST be ignored.
        self.icvFNinch          = (bits & 0x00020000) != 0  # whether the value of dxfpat.icvForeground MUST be ignored.
        self.icvBNinch          = (bits & 0x00040000) != 0  # whether the value of dxfpat.icvBackground MUST be ignored.
        self.ifmtNinch          = (bits & 0x00080000) != 0  # whether the value of dxfnum.ifmt MUST be ignored.
        self.fIfntNinch         = (bits & 0x00100000) != 0  # whether the value of dxffntd.ifnt MUST be ignored.
        self.V                  = (bits & 0x00200000) != 0  # (unused)
        self.W                  = (bits & 0x01C00000) != 0  # (reserved; 3-bits)
        self.ibitAtrNum         = (bits & 0x02000000) != 0  # whether number formatting information is part of this structure.
        self.ibitAtrFnt         = (bits & 0x04000000) != 0  # whether font information is part of this structure.
        self.ibitAtrAlc         = (bits & 0x08000000) != 0  # whether alignment information is part of this structure.
        self.ibitAtrBdr         = (bits & 0x10000000) != 0  # whether border formatting information is part of this structure.
        self.ibitAtrPat         = (bits & 0x20000000) != 0  # whether pattern information is part of this structure.
        self.ibitAtrProt        = (bits & 0x40000000) != 0  # whether rotation information is part of this structure.
        self.iReadingOrderNinch = (bits & 0x80000000) != 0  # whether the value of dxfalc.iReadingOrder MUST be ignored.
        bits = self.readUnsignedInt(2)
        self.fIfmtUser          = (bits & 0x0001) != 0  # When set to 1, dxfnum contains a format string.
        self.f                  = (bits & 0x0002) != 0  # (unused)
        self.fNewBorder         = (bits & 0x0004) != 0  # 0=border formats to all cells; 1=border formats to the range outline only
        self.fZeroInited        = (bits & 0x8000) != 0  # whether the value of dxfalc.iReadingOrder MUST be taken into account.

        if self.ibitAtrNum:
            # DXFNum (number format)
            if self.fIfmtUser:
                # DXFNumUser (string)
                sizeDXFNumUser = self.readUnsignedInt(2)
                strBytes = self.readBytes(sizeDXFNumUser)
                text, textLen = globals.getRichText(strBytes)
                self.numFmtName = text
            else:
                # DXFNumIFmt
                self.readUnsignedInt(1) # ignored
                self.numFmtID = self.readUnsignedInt(1)

        if self.ibitAtrFnt:
            # DXFFntD (font information)
            nameLen = self.readUnsignedInt(1)
            if nameLen > 0:
                # Note the text length may double in case of a double-byte string.
                curPos = self.getCurrentPos()
                self.fontName, nameLen = globals.getRichText(self.readRemainingBytes(), nameLen)
                self.setCurrentPos(curPos) # Move back to the pre-text position.
                self.moveForward(realLen)  # Move for exactly the bytes read.

            if 63 - nameLen < 0:
                raise RecordError

            self.readUnsignedInt(63 - nameLen) # Ignore these bytes.
            self.fontAttrs = self.readBytes(16) # I'll process this later.
            self.fontColor = self.readUnsignedInt(4)
            self.readUnsignedInt(4) # ignored
            tsNinch = self.readUnsignedInt(4)
            sssNinch = self.readUnsignedInt(4) != 0
            ulsNinch = self.readUnsignedInt(4) != 0
            blsNinch = self.readUnsignedInt(4) != 0
            self.readUnsignedInt(4) # ignored
            ich = self.readUnsignedInt(4)
            cch = self.readUnsignedInt(4)
            iFnt = self.readUnsignedInt(2)

        if self.ibitAtrAlc:
            # DXFALC (text alignment properties)
            self.readUnsignedInt(8)

        if self.ibitAtrBdr:
            # DXFBdr (border properties)
            self.readUnsignedInt(8)

        if self.ibitAtrPat:
            # DXFPat (pattern and colors)
            self.readUnsignedInt(4)

        if self.ibitAtrProt:
            # DXFProt (protection attributes)
            self.readUnsignedInt(2)

    conditionType = {
        0x01: "use comparison function",
        0x02: "use 1st formula"
    }

    compFunction = {
        0x01: "(v1 <= v2 && (v1 <= cell || cell == v2)) || (v2 < v1 && v2 <= cell && cell <= v1)",
        0x02: "v1 <= v2 && (cell < v1 || v2 < cell)",
        0x03: "cell == v1",
        0x04: "cell != v1",
        0x05: "v1 < cell",
        0x06: "cell < v1",
        0x07: "v1 <= cell",
        0x08: "cell <= v1"
    }

    def parseBytes (self):
        self.__parseBytes()

        # condition type
        condTypeName = globals.getValueOrUnknown(CF.conditionType, self.conditionType)
        self.appendLine("condition type: %s (0x%2.2X)"%(condTypeName, self.conditionType))

        # comparison function
        compFuncText = globals.getValueOrUnknown(CF.compFunction, self.compFunction)
        self.appendLine("comparison function: %s (0x%2.2X)"%(compFuncText, self.compFunction))

        # DXFN structure (TODO: This is not complete)
        if self.ibitAtrNum:
            if self.fIfmtUser:
                self.appendLine("number format to use: %s (name)"%self.numFmtName)
            else:
                self.appendLine("number format to use: %d (ID)"%self.numFmtID)

        # formulas

        if len(self.formula1) > 0:
            self.appendLine("formula 1 (bytes): %s"%globals.getRawBytes(self.formula1, True, False))
            parser = formula.FormulaParser(self.header, self.formula1)
            parser.parse()
            self.appendLine("formula 1 (displayed): " + parser.getText())

        if len(self.formula2) > 0:
            self.appendLine("formula 2 (bytes): %s"%globals.getRawBytes(self.formula2, True, False))
            parser = formula.FormulaParser(self.header, self.formula2)
            parser.parse()
            self.appendLine("formula 2 (displayed): " + parser.getText())       


class CondFmt(BaseRecordHandler):

    def __parseBytes (self):
        self.cfCount = self.readUnsignedInt(2)
        tmp = self.readUnsignedInt(2)
        self.toughRecalc = (tmp & 0x01) != 0
        self.recordID = (tmp & 0xFE) / 2
        self.refBound = Ref8U(self)

        hitRangeCount = self.readUnsignedInt(2)
        self.hitRanges = []
        for i in xrange(0, hitRangeCount):
            self.hitRanges.append(Ref8U(self))

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("record count: %d"%self.cfCount)
        self.appendLineBoolean("tough recalc", self.toughRecalc)
        self.appendLine("ID of this record: %d"%self.recordID)
        self.appendLine("format range: (col=%d,row=%d) - (col=%d,row=%d)"%
            (self.refBound.col1, self.refBound.row1, self.refBound.col2, self.refBound.row2))
        for hitRange in self.hitRanges:
            self.appendLine("hit range: (col=%d,row=%d) - (col=%d,row=%d)"%
                (hitRange.col1, hitRange.row1, hitRange.col2, hitRange.row2))

    def fillModel (self, model):
        self.__parseBytes()
        formatRange = formula.CellRange()
        formatRange.firstCol = self.refBound.col1
        formatRange.lastCol  = self.refBound.col2
        formatRange.firstRow = self.refBound.row1
        formatRange.lastRow  = self.refBound.row2
        obj = xlsmodel.CondFormat()
        obj.formatRange = formatRange
        sheet = model.getCurrentSheet()
        sheet.setCondFormat(obj)


class Dimensions(BaseRecordHandler):

    def __parseBytes (self):
        self.rowMin = self.readUnsignedInt(4)
        self.rowMax = self.readUnsignedInt(4)
        self.colMin = self.readUnsignedInt(2)
        self.colMax = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("first defined row: %d"%self.rowMin)
        self.appendLine("last defined row plus 1: %d"%self.rowMax)
        self.appendLine("first defined column: %d"%self.colMin)
        self.appendLine("last defined column plus 1: %d"%self.colMax)

    def fillModel (self, model):
        self.__parseBytes()
        sh = model.getCurrentSheet()
        sh.setFirstDefinedCell(self.colMin, self.rowMin)
        sh.setFirstFreeCell(self.colMax, self.rowMax)


class Dv(BaseRecordHandler):

    valueTypes = [
        'any type of value',               # 0x0 
        'whole number',                    # 0x1 
        'decimal value',                   # 0x2 
        'matches one in a list of values', # 0x3 
        'date value',                      # 0x4 
        'time value',                      # 0x5 
        'text value',                      # 0x6 
        'custom formula'                   # 0x7 
    ]

    errorStyles = [
        'stop icon',       # 0x00
        'warning icon',    # 0x01
        'information icon' # 0x02
    ]

    imeModes = [
        'No Control',              # 0x00 
        'On',                      # 0x01 
        'Off (English)',           # 0x02 
        'Hiragana',                # 0x04 
        'wide katakana',           # 0x05 
        'narrow katakana',         # 0x06 
        'Full-width alphanumeric', # 0x07 
        'Half-width alphanumeric', # 0x08 
        'Full-width hangul',       # 0x09 
        'Half-width hangul'        # 0x0A 
    ]

    operatorTypes = [
        'Between',                  # 0x0
        'Not Between',              # 0x1
        'Equals',                   # 0x2
        'Not Equals',               # 0x3
        'Greater Than',             # 0x4
        'Less Than',                # 0x5
        'Greater Than or Equal To', # 0x6
        'Less Than or Equal To'     # 0x7
    ]

    def __parseBytes (self):
        bits = self.readUnsignedInt(4)
        self.valType      = (bits & 0x0000000F)
        self.errStyle     = (bits & 0x00000070) / (2**4)
        self.strLookup    = (bits & 0x00000080) != 0
        self.allowBlank   = (bits & 0x00000100) != 0
        self.noDropDown   = (bits & 0x00000200) != 0
        self.imeMode      = (bits & 0x0003FC00) / (2**10)    # take 8 bits and shift by 10 bits
        self.showInputMsg = (bits & 0x00040000) != 0
        self.showErrorMsg = (bits & 0x00080000) != 0
        self.operator     = (bits & 0x00F00000) / (2**20)

        self.promptTitle = self.readUnicodeString()
        self.errorTitle = self.readUnicodeString()
        self.prompt = self.readUnicodeString()
        self.error = self.readUnicodeString()

        formulaLen = self.readUnsignedInt(2)
        self.readUnsignedInt(2) # ignore 2 bytes.
        self.formula1 = self.readBytes(formulaLen)
        self.strFormula1 = ''
        if len(self.formula1) > 0:
            parser = formula.FormulaParser(self.header, self.formula1)
            parser.parse()
            self.strFormula1 = parser.getText()

        formulaLen = self.readUnsignedInt(2)
        self.readUnsignedInt(2) # ignore 2 bytes.
        self.formula2 = self.readBytes(formulaLen)
        self.strFormula2 = ''
        if len(self.formula2) > 0:
            parser = formula.FormulaParser(self.header, self.formula2)
            parser.parse()
            self.strFormula2 = parser.getText()

        rangeCount = self.readUnsignedInt(2)
        self.ranges = []
        for i in xrange(0, rangeCount):
            obj = formula.CellRange()
            obj.firstRow = self.readUnsignedInt(2)
            obj.lastRow = self.readUnsignedInt(2)
            obj.firstCol = self.readUnsignedInt(2)
            obj.lastCol = self.readUnsignedInt(2)
            self.ranges.append(obj)

    def parseBytes (self):
        self.__parseBytes()
        s = globals.getValueOrUnknown(Dv.valueTypes, self.valType)
        self.appendLine("type: %s (0x%1.1X)"%(s, self.valType))
        s = globals.getValueOrUnknown(Dv.errorStyles, self.errStyle)
        self.appendLine("error style: %s (0x%1.1X)"%(s, self.errStyle))
        self.appendLineBoolean("list of valid inputs", self.strLookup)
        self.appendLineBoolean("allow blank", self.allowBlank)
        self.appendLineBoolean("suppress down-down in cell", self.noDropDown)
        s = globals.getValueOrUnknown(Dv.imeModes, self.imeMode)
        self.appendLine("IME mode: %s (0x%1.1X)"%(s, self.imeMode))
        self.appendLineBoolean("show input message", self.showInputMsg)
        self.appendLineBoolean("show error message", self.showErrorMsg)
        s = globals.getValueOrUnknown(Dv.operatorTypes, self.operator)
        self.appendLine("operator type: %s (0x%1.1X)"%(s, self.operator))
        self.appendLine("prompt title: %s"%self.promptTitle)
        self.appendLine("error title: %s"%self.errorTitle)
        self.appendLine("prompt: %s"%self.prompt)
        self.appendLine("error: %s"%self.error)
        self.appendLine("formula 1 (bytes): %s"%globals.getRawBytes(self.formula1, True, False))
        self.appendLine("formula 1 (displayed): %s"%self.strFormula1)

        self.appendLine("formula 2 (bytes): %s"%globals.getRawBytes(self.formula2, True, False))
        self.appendLine("formula 2 (displayed): %s"%self.strFormula2)

        for rng in self.ranges:
            self.appendLine("range: %s"%rng.getName())

    def fillModel (self, model):
        self.__parseBytes()
        obj = xlsmodel.DataValidation(self.ranges)
        obj.valueType = globals.getValueOrUnknown(Dv.valueTypes, self.valType)
        obj.errorStyle = globals.getValueOrUnknown(Dv.errorStyles, self.errStyle)
        obj.operator = globals.getValueOrUnknown(Dv.operatorTypes, self.operator)
        obj.showInputMsg = self.showInputMsg
        obj.showErrorMsg = self.showErrorMsg
        obj.strLookup = self.strLookup
        obj.allowBlank = self.allowBlank
        obj.prompt = self.prompt
        obj.promptTitle = self.promptTitle
        obj.error = self.error
        obj.errorTitle = self.errorTitle
        obj.formula1 = self.strFormula1
        obj.formula2 = self.strFormula2
        sheet = model.getCurrentSheet()
        sheet.setDataValidation(obj)

class DVal(BaseRecordHandler):

    def __parseBytes (self):
        bits = self.readUnsignedInt(2)
        self.winClosed = (bits & 0x0001) != 0
        self.left = self.readUnsignedInt(4)
        self.top = self.readUnsignedInt(4)
        self.objID = self.readSignedInt(4)
        self.dvCount = self.readUnsignedInt(4)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLineBoolean("window was closed", self.winClosed)
        self.appendLine("window position: (x=%d,y=%d)"%(self.left, self.top))
        s = ''
        if self.objID == -1:
            s = '(no drop-down displayed)'
        self.appendLine("drop-down button object ID: %d %s"%(self.objID, s))
        self.appendLine("number of DV records: %d"%self.dvCount)

    def fillModel (self, model):
        self.__parseBytes()

class Fbi(BaseRecordHandler):
    def __parseBytes (self):
        self.fontWidth = self.readUnsignedInt(2)
        self.fontHeight = self.readUnsignedInt(2)
        self.defaultHeight = self.readUnsignedInt(2)
        self.scaleType = self.readUnsignedInt(2)
        self.fontID = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("font width (twips): %d"%self.fontWidth)
        self.appendLine("font height (twips): %d"%self.fontHeight)
        self.appendLine("default font height (twips): %d"%self.defaultHeight)
        if self.scaleType == 0:
            s = "chart area"
        else:
            s = "plot area"
        self.appendLine("scale by: %s"%s)
        self.appendLine("font ID: %d"%self.fontID)


class FilePass(BaseRecordHandler):

    def parseBytes (self):
        mode = self.readUnsignedInt(2)    # mode: 0 = BIFF5  1 = BIFF8
        self.readUnsignedInt(2)           # ignore 2 bytes.
        subMode = self.readUnsignedInt(2) # submode: 1 = standard encryption  2 = strong encryption

        modeName = 'unknown'
        if mode == 0:
            modeName = 'BIFF5'
        elif mode == 1:
            modeName = 'BIFF8'

        encType = 'unknown'
        if subMode == 1:
            encType = 'standard'
        elif subMode == 2:
            encType = 'strong'
        
        self.appendLine("mode: %s"%modeName)
        self.appendLine("encryption type: %s"%encType)
        self.appendLine("")
        self.appendMultiLine("NOTE: Since this document appears to be encrypted, the dumper will not parse the record contents from this point forward.")


class FilterMode(BaseRecordHandler):

    def parseBytes (self):
        self.appendMultiLine("NOTE: The presence of this record indicates that the sheet has a filtered list.")


class Format(BaseRecordHandler):

    def __parseBytes (self):
        self.numfmtID = self.readUnsignedInt(2)
        self.code = self.readUnicodeString()

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("index: %d"%self.numfmtID)
        self.appendLine("code: %s"%globals.encodeName(self.code))


class Formula(BaseRecordHandler):

    def __parseBytes (self):
        self.row = self.readUnsignedInt(2)
        self.col = self.readUnsignedInt(2)
        self.xf = self.readUnsignedInt(2)
        self.fval = self.readDouble()

        flag = self.readUnsignedInt(2)
        self.recalc         = (flag & 0x0001) != 0 # A
        reserved            = (flag & 0x0002) != 0 # B
        self.fillAlignment  = (flag & 0x0004) != 0 # C
        self.sharedFormula  = (flag & 0x0008) != 0 # D
        reserved            = (flag & 0x0010) != 0 # E
        self.clearErrors    = (flag & 0x0020) != 0 # F

        self.appCacheInfo = self.readUnsignedInt(4) # used only for app-specific optimization.  Ignore it for now.
        tokenSize = self.readUnsignedInt(2)
        self.tokens = self.readBytes(tokenSize)

    def parseBytes (self):
        self.__parseBytes()
        fparser = formula.FormulaParser(self.header, self.tokens)
        try:
            fparser.parse()
            ftext = fparser.getText()
        except formula.FormulaParserError as e:
            ftext = "(Error: %s)"%e.args[0]

        self.appendCellPosition(self.col, self.row)
        self.appendLine("XF record ID: %d"%self.xf)
        self.appendLine("formula result: %g"%self.fval)
        self.appendLineBoolean("recalculate always", self.recalc)
        self.appendLineBoolean("fill or center across selection", self.fillAlignment)
        self.appendLineBoolean("shared formula", self.sharedFormula)
        self.appendLineBoolean("clear errors", self.clearErrors)
        self.appendLine("formula bytes: %s"%globals.getRawBytes(self.tokens, True, False))
        self.appendLine("formula string: "+ftext)

    def fillModel (self, model):
        self.__parseBytes()
        sheet = model.getCurrentSheet()
        cell = xlsmodel.FormulaCell()
        cell.tokens = self.tokens
        cell.cachedResult = self.fval
        sheet.setCell(self.col, self.row, cell)


class HorBreaks(BaseRecordHandler):
    """Stores all horizontal breaks in a sheet."""

    def __parseBytes (self):
        self.count = self.readUnsignedInt(2)
        self.breaks = []
        for i in xrange(0, self.count):
            row = self.readUnsignedInt(2)
            col1 = self.readUnsignedInt(2)
            col2 = self.readUnsignedInt(2)
            self.breaks.append((row, col1, col2))

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("count: %d"%self.count)
        for i in xrange(0, self.count):
            self.appendLine("break: (row: %d; colums: %d-%d)"%self.breaks[i])


class Array(BaseRecordHandler):

    def __parseBytes (self):
        self.ref = RefU(self)
        flag = self.readUnsignedInt(2)
        self.alwaysCalc = (flag & 0x0001) != 0
        unused = self.readBytes(4)
        tokenSize = self.readUnsignedInt(2)
        self.tokens = self.readBytes(tokenSize)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("range: %s"%self.ref.toString())
        self.appendLineBoolean("always calc", self.alwaysCalc)
        fparser = formula.FormulaParser(self.header, self.tokens)
        fparser.parse()
        self.appendLine("formula bytes: %s"%globals.getRawBytes(self.tokens, True, False))
        self.appendLine("formula string: %s"%fparser.getText())

class Label(BaseRecordHandler):

    def __parseBytes (self):
        self.col = self.readUnsignedInt(2)
        self.row = self.readUnsignedInt(2)
        self.xfIdx = self.readUnsignedInt(2)
        textLen = self.readUnsignedInt(2)
        self.text, textLen = globals.getRichText(self.readRemainingBytes(), textLen)

    def parseBytes (self):
        self.__parseBytes()
        self.appendCellPosition(self.col, self.row)
        self.appendLine("XF record ID: %d"%self.xfIdx)
        self.appendLine("label text: %s"%self.text)


class LabelSST(BaseRecordHandler):

    def __parseBytes (self):
        self.row = self.readUnsignedInt(2)
        self.col = self.readUnsignedInt(2)
        self.xfIdx = self.readUnsignedInt(2)
        self.strId = self.readUnsignedInt(4)

    def parseBytes (self):
        self.__parseBytes()
        self.appendCellPosition(self.col, self.row)
        self.appendLine("XF record ID: %d"%self.xfIdx)
        self.appendLine("string ID in SST: %d"%self.strId)

    def fillModel (self, model):
        self.__parseBytes()
        sheet = model.getCurrentSheet()
        cell = xlsmodel.LabelCell()
        cell.strID = self.strId
        sheet.setCell(self.col, self.row, cell)


class MulRK(BaseRecordHandler):
    class RKRec(object):
        def __init__ (self):
            self.xfIdx = None    # XF record index
            self.number = None   # RK number

    def __parseBytes (self):
        self.row = self.readUnsignedInt(2)
        self.col1 = self.readUnsignedInt(2)
        self.rkrecs = []
        rkCount = (self.getSize() - self.getCurrentPos() - 2) / 6
        for i in xrange(0, rkCount):
            rec = MulRK.RKRec()
            rec.xfIdx = self.readUnsignedInt(2)
            rec.number = self.readUnsignedInt(4)
            self.rkrecs.append(rec)

        self.col2 = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("row: %d"%self.row)
        self.appendLine("columns: %d - %d"%(self.col1, self.col2))
        for rkrec in self.rkrecs:
            self.appendLine("XF record ID: %d"%rkrec.xfIdx)
            self.appendLine("RK number: %g"%decodeRK(rkrec.number))

    def fillModel (self, model):
        self.__parseBytes()
        sheet = model.getCurrentSheet()
        n = len(self.rkrecs)
        for i in xrange(0, n):
            rkrec = self.rkrecs[i]
            col = self.col1 + i
            cell = xlsmodel.NumberCell(decodeRK(rkrec.number))
            sheet.setCell(col, self.row, cell)

class MulBlank(BaseRecordHandler):

    def __parseBytes (self):
        self.row = self.readUnsignedInt(2)
        self.col1 = self.readUnsignedInt(2)
        self.col2 = -1
        self.xfCells = []
        while True:
            val = self.readUnsignedInt(2)
            if self.isEndOfRecord():
                self.col2 = val
                break
            self.xfCells.append(val)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("row: %d"%self.row)
        self.appendLine("columns: %d-%d"%(self.col1, self.col2))
        s = "XF Record IDs:"
        for xfCell in self.xfCells:
            s += " %d"%xfCell
        self.appendMultiLine(s)


class Number(BaseRecordHandler):

    def parseBytes (self):
        row = globals.getSignedInt(self.bytes[0:2])
        col = globals.getSignedInt(self.bytes[2:4])
        xf  = globals.getSignedInt(self.bytes[4:6])
        fval = globals.getDouble(self.bytes[6:14])
        self.appendCellPosition(col, row)
        self.appendLine("XF record ID: %d"%xf)
        self.appendLine("value: %g"%fval)


class Obj(BaseRecordHandler):

    ftEnd      = 0x00 # End of OBJ record
                      # 0x01 - 0x03 (reserved)
    ftMacro    = 0x04 # Fmla-style macro
    ftButton   = 0x05 # Command button
    ftGmo      = 0x06 # Group marker
    ftCf       = 0x07 # Clipboard format
    ftPioGrbit = 0x08 # Picture option flags
    ftPictFmla = 0x09 # Picture fmla-style macro
    ftCbls     = 0x0A # Check box link
    ftRbo      = 0x0B # Radio button
    ftSbs      = 0x0C # Scroll bar
    ftNts      = 0x0D # Note structure
    ftSbsFmla  = 0x0E # Scroll bar fmla-style macro
    ftGboData  = 0x0F # Group box data
    ftEdoData  = 0x10 # Edit control data
    ftRboData  = 0x11 # Radio button data
    ftCblsData = 0x12 # Check box data
    ftLbsData  = 0x13 # List box data
    ftCblsFmla = 0x14 # Check box link fmla-style macro
    ftCmo      = 0x15 # Common object data

    class Cmo:
        Types = [
            'Group',                   # 0x00
            'Line',                    # 0x01
            'Rectangle',               # 0x02
            'Oval',                    # 0x03
            'Arc',                     # 0x04
            'Chart',                   # 0x05
            'Text',                    # 0x06
            'Button',                  # 0x07
            'Picture',                 # 0x08
            'Polygon',                 # 0x09
            '(Reserved)',              # 0x0A
            'Check box',               # 0x0B
            'Option button',           # 0x0C
            'Edit box',                # 0x0D
            'Label',                   # 0x0E
            'Dialog box',              # 0x0F
            'Spinner',                 # 0x10
            'Scroll bar',              # 0x11
            'List box',                # 0x12
            'Group box',               # 0x13
            'Combo box',               # 0x14
            '(Reserved)',              # 0x15
            '(Reserved)',              # 0x16
            '(Reserved)',              # 0x17
            '(Reserved)',              # 0x18
            'Comment',                 # 0x19
            '(Reserved)',              # 0x1A
            '(Reserved)',              # 0x1B
            '(Reserved)',              # 0x1C
            '(Reserved)',              # 0x1D
            'Microsoft Office drawing' # 0x1E
        ]

        @staticmethod
        def getType (typeID):
            if len(Obj.Cmo.Types) > typeID:
                return Obj.Cmo.Types[typeID]
            return "(unknown) (0x%2.2X)"%typeID

    def parseBytes (self):
        while not self.isEndOfRecord():
            fieldType = self.readUnsignedInt(2)
            fieldSize = self.readUnsignedInt(2)
            if fieldType == Obj.ftEnd:
                # reached the end of OBJ record.
                return

            if fieldType == Obj.ftCmo:
                self.parseCmo(fieldSize)
            else:
                fieldBytes = self.readBytes(fieldSize)
                self.appendLine("field 0x%2.2X: %s"%(fieldType, globals.getRawBytes(fieldBytes, True, False)))

    def parseCmo (self, size):
        if size != 18:
            # size of Cmo must be 18.  Something is wrong here.
            self.readBytes(size)
            globals.error("parsing of common object field in OBJ failed due to invalid size.")
            return

        objType = self.readUnsignedInt(2)
        objID  = self.readUnsignedInt(2)
        flag   = self.readUnsignedInt(2)

        # the rest of the bytes are reserved & should be all zero.
        unused1 = self.readUnsignedInt(4)
        unused2 = self.readUnsignedInt(4)
        unused3 = self.readUnsignedInt(4)

        self.appendLine("common object: ")
        self.appendLine("  type: %s (0x%2.2X)"%(Obj.Cmo.getType(objType), objType))
        self.appendLine("  object ID: %d"%objID)

        # 0    0001h fLocked    =1 if the object is locked when the sheet is protected
        # 3-1  000Eh (Reserved) Reserved; must be 0 (zero)
        # 4    0010h fPrint     =1 if the object is printable
        # 12-5 1FE0h (Reserved) Reserved; must be 0 (zero)
        # 13   2000h fAutoFill  =1 if the object uses automatic fill style
        # 14   4000h fAutoLine  =1 if the object uses automatic line style
        # 15   8000h (Reserved) Reserved; must be 0 (zero)

        locked          = (flag & 0x0001) != 0 # A
                                               # B
        defaultSize     = (flag & 0x0004) != 0 # C
        published       = (flag & 0x0008) != 0 # D
        printable       = (flag & 0x0010) != 0 # E
                                               # F
                                               # G
        disabled        = (flag & 0x0080) != 0 # H
        UIObj           = (flag & 0x0100) != 0 # I
        recalcObj       = (flag & 0x0200) != 0 # J
                                               # K
                                               # L
        recalcObjAlways = (flag & 0x1000) != 0 # M
        autoFill        = (flag & 0x2000) != 0 # N
        autoLine        = (flag & 0x4000) != 0 # O
        self.appendLineBoolean("  locked", locked)
        self.appendLineBoolean("  default size", defaultSize)
        self.appendLineBoolean("  printable", printable)
        self.appendLineBoolean("  automatic fill style", autoFill)
        self.appendLineBoolean("  automatic line style", autoLine)

class PlotGrowth(BaseRecordHandler):

    def __parseBytes (self):
        self.dx = self.readFixedPoint()
        self.dy = self.readFixedPoint()

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("horizontal growth: %g"%self.dx)
        self.appendLine("vertical growth: %g"%self.dy)

class PrintSize(BaseRecordHandler):

    Types = [
        "unchanged from the defaults in the workbook",
        "resized non-proportionally to fill the entire page",
        "resized proportionally to fill the entire page",
        "size defined in the chart record"
    ]

    def __parseBytes (self):
        self.typeID = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine(globals.getValueOrUnknown(PrintSize.Types, self.typeID))

class Protect(BaseRecordHandler):

    def __parseBytes (self):
        self.locked = self.readUnsignedInt(2) != 0

    def parseBytes (self):
        self.__parseBytes()
        self.appendLineBoolean("workbook locked", self.locked)


class RK(BaseRecordHandler):
    """Cell with encoded integer or floating-point value"""

    def parseBytes (self):
        row = globals.getSignedInt(self.bytes[0:2])
        col = globals.getSignedInt(self.bytes[2:4])
        xf  = globals.getSignedInt(self.bytes[4:6])

        rkval = globals.getSignedInt(self.bytes[6:10])
        auxData = RKAuxData()
        realVal = decodeRK(rkval, auxData)

        self.appendCellPosition(col, row)
        self.appendLine("XF record ID: %d"%xf)
        self.appendLine("multiplied by 100: %d"%auxData.multi100)
        if auxData.signedInt:
            self.appendLine("type: signed integer")
        else:
            self.appendLine("type: floating point")
        self.appendLine("value: %g"%realVal)

class Scl(BaseRecordHandler):

    def __parseBytes (self):
        self.numerator = self.readSignedInt(2)
        self.denominator = self.readSignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        val = 0.0 # force the value to be treated as double precision.
        val += self.numerator
        val /= self.denominator
        self.appendLine("zoom level: %g"%val)

class SeriesText(BaseRecordHandler):

    def __parseBytes (self):
        self.readBytes(2) # must be zero, ignored.
        self.text = self.readShortXLUnicodeString()

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("text: '%s'"%self.text)


class String(BaseRecordHandler):
    """Cached string formula result for preceding formula record."""

    def __parseBytes (self):
        strLen = globals.getSignedInt(self.bytes[0:1])
        self.name, byteLen = globals.getRichText(self.bytes[2:], strLen)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("string value: '%s'"%self.name)

    def fillModel (self, model):
        self.__parseBytes()
        cell = model.getCurrentSheet().getLastCell()
        if cell.modelType == xlsmodel.CellBase.Type.Formula:
            cell.cachedResult = self.name


class SST(BaseRecordHandler):

    def __parseBytes (self):
        self.refCount = self.readSignedInt(4) # total number of references in workbook
        self.strCount = self.readSignedInt(4) # total number of unique strings.
        self.sharedStrings = []
        for i in xrange(0, self.strCount):
            extText, bytesRead = globals.getUnicodeRichExtText(self.bytes[self.getCurrentPos():])
            self.readBytes(bytesRead) # advance current position.
            self.sharedStrings.append(extText)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("total number of references: %d"%self.refCount)
        self.appendLine("total number of unique strings: %d"%self.strCount)
        i = 0
        for s in self.sharedStrings:
            self.appendLine("s%d: %s"%(i, globals.encodeName(s.baseText)))
            i += 1

    def fillModel (self, model):
        self.__parseBytes()
        wbg = model.getWorkbookGlobal()
        for sst in self.sharedStrings:
            wbg.appendSharedString(sst)


class Blank(BaseRecordHandler):

    def parseBytes (self):
        row = globals.getSignedInt(self.bytes[0:2])
        col = globals.getSignedInt(self.bytes[2:4])
        xf  = globals.getSignedInt(self.bytes[4:6])
        self.appendCellPosition(col, row)
        self.appendLine("XF record ID: %d"%xf)


class DBCell(BaseRecordHandler):

    def parseBytes (self):
        rowRecOffset = self.readUnsignedInt(4)
        self.appendLine("offset to first ROW record: %d"%rowRecOffset)
        while not self.isEndOfRecord():
            cellOffset = self.readUnsignedInt(2)
            self.appendLine("offset to CELL record: %d"%cellOffset)
        return


class DefColWidth(BaseRecordHandler):

    def parseBytes (self):
        w = self.readUnsignedInt(2)
        self.appendLine("default column width (in characters): %d"%w)


class DefRowHeight(BaseRecordHandler):

    def __parseBytes (self):
        flag = self.readUnsignedInt(1)
        self.readUnsignedInt(1) # ignore 1 byte.
        self.unsynced = (flag & 0x01) != 0
        self.dyZero   = (flag & 0x02) != 0
        self.exAsc    = (flag & 0x04) != 0
        self.exDsc    = (flag & 0x08) != 0
        self.rowHeight = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLineBoolean("default row height settings changed", self.unsynced)
        self.appendLineBoolean("empty rows have a height of zero", self.dyZero)
        self.appendLineBoolean("empty rows have a thick border style at top", self.exAsc)
        self.appendLineBoolean("empty rows have a thick border style at bottom", self.exDsc)
        if self.dyZero:
            self.appendLine("default height for hidden rows: %d"%self.rowHeight)
        else:
            self.appendLine("default height for empty rows: %d"%self.rowHeight)


class ColInfo(BaseRecordHandler):

    def parseBytes (self):
        colFirst = self.readUnsignedInt(2)
        colLast  = self.readUnsignedInt(2)
        coldx    = self.readUnsignedInt(2)
        ixfe     = self.readUnsignedInt(2)
        flags    = self.readUnsignedInt(2)

        isHidden = (flags & 0x0001)
        outlineLevel = (flags & 0x0700)/4
        isCollapsed = (flags & 0x1000)/4

        self.appendLine("formatted columns: %d - %d"%(colFirst,colLast))
        self.appendLine("column width (in 1/256s of a char): %d"%coldx)
        self.appendLine("XF record index: %d"%ixfe)
        self.appendLine("hidden: %s"%self.getYesNo(isHidden))
        self.appendLine("outline level: %d"%outlineLevel)
        self.appendLine("collapsed: %s"%self.getYesNo(isCollapsed))


class Row(BaseRecordHandler):

    def __parseBytes (self):
        self.row  = self.readUnsignedInt(2)
        self.col1 = self.readUnsignedInt(2)
        self.col2 = self.readUnsignedInt(2)

        flag = self.readUnsignedInt(2)
        self.rowHeight     = (flag & 0x7FFF)
        self.defaultHeight = ((flag & 0x8000) != 0)
        self.irwMac = self.readUnsignedInt(2)

        dummy = self.readUnsignedInt(2)
        flag = self.readUnsignedInt(2)
        self.outLevel   = (flag & 0x0007)
        self.collapsed  = (flag & 0x0010)
        self.zeroHeight = (flag & 0x0020) 
        self.unsynced   = (flag & 0x0040)
        self.ghostDirty = (flag & 0x0080)

    def parseBytes (self):
        self.__parseBytes()

        self.appendLine("row: %d; col: %d - %d"%(self.row, self.col1, self.col2))
        self.appendLine("row height (twips): %d"%self.rowHeight)

        if self.defaultHeight:
            self.appendLine("row height type: default")
        else:
            self.appendLine("row height type: custom")

        self.appendLine("optimize flag (0 for BIFF): %d"%self.irwMac)

        self.appendLine("outline level: %d"%self.outLevel)
        self.appendLine("collapsed: %s"%self.getYesNo(self.collapsed))
        self.appendLine("zero height: %s"%self.getYesNo(self.zeroHeight))
        self.appendLine("unsynced: %s"%self.getYesNo(self.unsynced))
        self.appendLine("ghost dirty: %s"%self.getYesNo(self.ghostDirty))

    def fillModel (self, model):
        self.__parseBytes()
        sh = model.getCurrentSheet()
        # store whether or not this row is hidden.
        if self.zeroHeight:
            sh.setRowHidden(self.row)
        sh.setRowHeight(self.row, self.rowHeight)


class Name(BaseRecordHandler):
    """Internal defined name (aka Lbl)"""

    builtInNames = [
        "Consolidate_Area",  # 0x00
        "Auto_Open       ",  # 0x01
        "Auto_Close      ",  # 0x02
        "Extract         ",  # 0x03
        "Database        ",  # 0x04
        "Criteria        ",  # 0x05
        "Print_Area      ",  # 0x06
        "Print_Titles    ",  # 0x07
        "Recorder        ",  # 0x08
        "Data_Form       ",  # 0x09
        "Auto_Activate   ",  # 0x0A
        "Auto_Deactivate ",  # 0x0B
        "Sheet_Title     ",  # 0x0C
        "_FilterDatabase "   # 0x0D
    ]

    funcCategories = [
        'All',              # 00
        'Financial',        # 01
        'DateTime',         # 02
        'MathTrigonometry', # 03
        'Statistical',      # 04
        'Lookup',           # 05
        'Database',         # 06
        'Text',             # 07
        'Logical',          # 08
        'Info',             # 09
        'Commands',         # 10
        'Customize',        # 11
        'MacroControl',     # 12
        'DDEExternal',      # 13
        'UserDefined',      # 14
        'Engineering',      # 15
        'Cube'              # 16
    ]

    @staticmethod
    def getBuiltInName (name):
        return globals.getValueOrUnknown(Name.builtInNames, ord(name[0]))

    @staticmethod
    def getFuncCategory (val):
        return globals.getValueOrUnknown(Name.funcCategories, val)

    def __writeOptionFlags (self):
        self.appendLine("option flags:")

        if self.isHidden:
            self.appendLine("  hidden")
        else:
            self.appendLine("  visible")

        if self.isMacroName:
            self.appendLine("  macro name")
            if self.isFuncMacro:
                self.appendLine("  function macro")
                self.appendLine("  function group: %d"%self.funcGrp)
            else:
                self.appendLine("  command macro")
            if self.isVBMacro:
                self.appendLine("  visual basic macro")
            else:
                self.appendLine("  sheet macro")
        else:
            self.appendLine("  standard name")

        if self.isComplFormula:
            self.appendLine("  complex formula - can return an array")
        else:
            self.appendLine("  simple formula")
        if self.isBuiltinName:
            self.appendLine("  built-in name")
        else:
            self.appendLine("  user-defined name")

        self.appendLineBoolean("  published", self.isPublished)
        self.appendLineBoolean("  workbook parameter", self.isWorkbookParam)


    def __parseBytes (self):
        flag = self.readUnsignedInt(2)
        self.isHidden        = (flag & 0x0001) != 0
        self.isFuncMacro     = (flag & 0x0002) != 0
        self.isVBMacro       = (flag & 0x0004) != 0
        self.isMacroName     = (flag & 0x0008) != 0
        self.isComplFormula  = (flag & 0x0010) != 0
        self.isBuiltinName   = (flag & 0x0020) != 0
        self.funcGrp         = (flag & 0x0FC0) / 64
        reserved             = (flag & 0x1000) != 0
        self.isPublished     = (flag & 0x2000) != 0
        self.isWorkbookParam = (flag & 0x4000) != 0
        reserved             = (flag & 0x8000) != 0

        self.keyShortCut      = self.readUnsignedInt(1)
        nameLen               = self.readUnsignedInt(1)
        self.formulaLen       = self.readUnsignedInt(2)
        self.readUnsignedInt(2) # 2-bytes reserved

        # 1-based index into the sheets in the current book, where the list is
        # arranged by the visible order of the tabs.
        self.sheetId = self.readUnsignedInt(2)

        # these optional texts may come after the formula token bytes.
        # NOTE: [MS-XLS] spec says these bytes are reserved and to be ignored.
        self.menuTextLen = self.readUnsignedInt(1)
        self.descTextLen = self.readUnsignedInt(1)
        self.helpTextLen = self.readUnsignedInt(1)
        self.statTextLen = self.readUnsignedInt(1)

        pos = self.getCurrentPos()
        self.name, byteLen = globals.getRichText(self.bytes[pos:], nameLen)
        self.readBytes(byteLen)
        self.tokenBytes = self.readBytes(self.formulaLen)

    def parseBytes (self):
        self.__parseBytes()

        tokenText = globals.getRawBytes(self.tokenBytes, True, False)
        o = formula.FormulaParser(self.header, self.tokenBytes)
        o.parse()
        formulaText = o.getText()
        self.appendLine("name: %s"%globals.encodeName(self.name))

        # is this name global or sheet-local?
        s = "global or local: "
        if self.sheetId == 0:
            s += "global"
        else:
            s += "local (1-based sheet ID = %d)"%self.sheetId
        self.appendLine(s)

        if self.isBuiltinName:
            self.appendLine("built-in name: %s"%Name.getBuiltInName(self.name))

        self.appendLine("function category: %s (%d)"%(Name.getFuncCategory(self.funcGrp), self.funcGrp))
        self.__writeOptionFlags()

#       self.appendLine("menu text length: %d"%self.menuTextLen)
#       self.appendLine("description length: %d"%self.descTextLen)
#       self.appendLine("help tip text length: %d"%self.helpTextLen)
#       self.appendLine("status bar text length: %d"%self.statTextLen)
        self.appendLine("formula length: %d"%self.formulaLen)
        self.appendLine("formula bytes: " + tokenText)
        self.appendLine("formula: " + formulaText)

    def fillModel (self, model):
        self.__parseBytes()

        wbg = model.getWorkbookGlobal()
        if self.isBuiltinName and len(self.name) == 1 and ord(self.name[0]) == 0x0D:
            # Pick up a database range for autofilter.
            wbg.setFilterRange(self.sheetId-1, self.tokenBytes)


class SupBook(BaseRecordHandler):
    """Supporting workbook"""

    class Type:
        Self  = 0x0401
        AddIn = 0x3A01

    def __parseBytes (self):
        self.ctab = self.readUnsignedInt(2)
        self.sbType = self.readUnsignedInt(2)

        if self.sbType > 0x00FF or self.sbType == 0x0000:
            return

        self.names = []
        isFirst = True
        self.moveBack(2)
        pos = self.getCurrentPos()
        while pos < self.size:
            ret, bytesLen = globals.getUnicodeRichExtText(self.bytes[pos:])
            name = ret.baseText
            self.moveForward(bytesLen)
            self.names.append(name)
            pos = self.getCurrentPos()

    def parseBytes (self):
        self.__parseBytes()
        if self.sbType == SupBook.Type.Self:
            # self-referencing supbook
            self.appendLine("type: self-referencing")
            self.appendLine("sheet name count: %d"%self.ctab)
            return

        if self.sbType == SupBook.Type.AddIn:
            self.appendLine("type: add-in referencing")
            self.appendMultiLine("Add-in function name stored in the following EXTERNNAME record.")
            return

        self.appendLine("sheet name count: %d"%self.ctab)
        if len(self.names) == 0:
            return

        self.appendLine("document URL: %s"%globals.encodeName(self.names[0]))
        for name in self.names[1:]:
            name = globals.encodeName(name)
            self.appendLine("sheet name: %s"%name)

    def fillModel (self, model):
        self.__parseBytes()
        wbg = model.getWorkbookGlobal()
        if self.sbType == SupBook.Type.Self:
            sb = xlsmodel.SupbookSelf(self.ctab)
            wbg.appendSupbook(sb)
        elif self.sbType == SupBook.Type.AddIn:
            # generic supbook instance just to keep the indices in sync.
            wbg.appendSupbook(xlsmodel.Supbook())
        else:
            # external document supbook
            sb = xlsmodel.SupbookExternal()
            sb.docURL = self.names[0]
            for name in self.names[1:]:
                sb.appendSheetName(name)
            wbg.appendSupbook(sb)


class ExternSheet(BaseRecordHandler):

    def __parseBytes (self):
        self.sheets = []
        num = self.readUnsignedInt(2)
        for i in xrange(0, num):
            book = self.readUnsignedInt(2)
            sheet1 = self.readUnsignedInt(2)
            sheet2 = self.readUnsignedInt(2)
            self.sheets.append((book, sheet1, sheet2))

    def parseBytes (self):
        self.__parseBytes()
        for sh in self.sheets:
            self.appendLine("SUPBOOK record ID: %d  (sheet ID range: %d - %d)"%(sh[0], sh[1], sh[2]))

    def fillModel (self, model):
        self.__parseBytes()
        wbg = model.getWorkbookGlobal()
        for sh in self.sheets:
            wbg.appendExternSheet(sh[0], sh[1], sh[2])


class ExternName(BaseRecordHandler):

    class MOper(object):
        Errors = {
            0x00: '#NULL!' ,
            0x07: '#DIV/0!',
            0x0F: '#VALUE!',
            0x17: '#REF!'  ,
            0x1D: '#NAME?' ,
            0x24: '#NUM!'  ,
            0x2A: '#N/A'
        }

        def __init__ (self, bytes):
            self.strm = globals.ByteStream(bytes)

        def parse (self):
            self.lastCol = self.strm.readUnsignedInt(1)
            self.lastRow = self.strm.readUnsignedInt(2)
            self.values = []
            n = (self.lastCol+1)*(self.lastRow+1)
            for i in xrange(0, n):
                # parse each value
                oc = self.strm.readUnsignedInt(1)
                if oc == 0x01:
                    # number
                    val = self.strm.readDouble()
                    self.values.append(val)
                elif oc == 0x02:
                    # string
                    s = self.strm.readUnicodeString()
                    self.values.append(s)
                elif oc == 0x04:
                    # boolean
                    b = self.strm.readUnsignedInt(1) != 0
                    self.strm.readBytes(7)
                    self.values.append(b)
                elif oc == 0x10:
                    # error
                    err = self.strm.readUnsignedInt(1)
                    self.strm.readBytes(7)
                    self.values.append(err)
                else:
                    # null value
                    self.strm.readBytes(8)
                    self.values.append(None)

        def output (self, hdl):
            hdl.appendLine("last column: %d"%self.lastCol)
            hdl.appendLine("last row: %d"%self.lastRow)
            for value in self.values:
                if type(value) == type(0.0):
                    hdl.appendLine("value: %g"%value)
                elif type(value) == type("s"):
                    hdl.appendLine("value: %s"%value)
                elif type(value) == type(True):
                    hdl.appendLine("value: %d (boolean)"%value)
                elif type(value) == type(1):
                    # error code stored as an integer.
                    if ExternName.MOper.Errors.has_key(value):
                        hdl.appendLine("value: %s"%ExternName.MOper.Errors[value])
                    else:
                        hdl.appendLine("value: 0x%2.2X (unknown error)"%value)
                else:
                    hdl.appendLine("value: (unknown)")

    def __parseBytes (self):
        flag = self.readUnsignedInt(2)

        self.isBuiltinName = (flag & 0x0001) != 0
        self.automatic     = (flag & 0x0002) != 0
        self.wantPict      = (flag & 0x0004) != 0
        self.isOLE         = (flag & 0x0008) != 0
        self.isOLELink     = (flag & 0x0010) != 0

        # 5 - 14 bits stores last successful clip format
        self.clipFormat    = (flag & 0x7FE0) / 2**5

        self.displayAsIcon = (flag & 0x8000) != 0

        if self.isOLELink:
            # next 4 bytes are 32-bit storage ID
            self.storageID = self.readUnsignedInt(4)
            nameLen = self.readUnsignedInt(1)
            self.name = self.readUnicodeString(nameLen)
            self.moper = self.readRemainingBytes()
        else:
            # assume external defined name (could be DDE link).
            # TODO: differentiate DDE link from external defined name.

            self.supbookID = self.readUnsignedInt(2)
            reserved = self.readUnsignedInt(2)
            nameLen = self.readUnsignedInt(1)
            self.name = self.readUnicodeString(nameLen)
            self.tokens = self.readRemainingBytes()

    def parseBytes (self):
        self.__parseBytes()

        self.appendLineBoolean("built-in name", self.isBuiltinName)
        self.appendLineBoolean("auto DDE or OLE", self.automatic)
        self.appendLineBoolean("use picture format", self.wantPict)
        self.appendLineBoolean("OLE", self.isOLE)
        self.appendLineBoolean("OLE Link", self.isOLELink)
        self.appendLine("clip format: %d"%self.clipFormat)
        self.appendLineBoolean("display as icon", self.displayAsIcon)

        if self.isOLELink:
            self.appendLine("type: OLE")
            self.appendLine("storage ID: 0x%4.4X"%self.storageID)
            self.appendLine("name: %s"%self.name)
            if len(self.moper) > 0:
                try:
                    parser = ExternName.MOper(self.moper)
                    parser.parse()
                    parser.output(self)
                except:
                    self.appendLine("Error while parsing the moper bytes.")
        else:
            # TODO: Test this.
            self.appendLine("type: defined name")
            if self.supbookID == 0:
                self.appendLine("sheet ID: 0 (global defined names)")
            else:
                self.appendLine("sheet ID: %d"%self.supbookID)

            self.appendLine("name: %s"%self.name)
            tokenText = globals.getRawBytes(self.tokens, True, False)
            self.appendLine("formula bytes: %s"%tokenText)

            # parse formula tokens
            o = formula.FormulaParser(self.header, self.tokens)
            o.parse()
            ftext = o.getText()
            self.appendLine("formula: %s"%ftext)

class Xct(BaseRecordHandler):

    def __parseBytes (self):
        self.crnCount = self.readSignedInt(2)
        self.sheetIndex = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("CRN count: %d"%self.crnCount)
        self.appendLine("index of referenced sheet in the SUPBOOK record: %d"%self.sheetIndex)

    def fillModel (self, model):
        self.__parseBytes()
        sb = model.getWorkbookGlobal().getLastSupbook()
        # this must be an external document supbook.
        if sb.type != xlsmodel.Supbook.Type.External:
            return
        sb.setCurrentSheet(self.sheetIndex)


class Crn(BaseRecordHandler):

    def __parseBytes (self):
        self.lastCol = self.readUnsignedInt(1)
        self.firstCol = self.readUnsignedInt(1)
        self.rowIndex = self.readUnsignedInt(2)
        self.cells = []
        for i in xrange(0, self.lastCol-self.firstCol+1):
            typeId = self.readUnsignedInt(1)
            if typeId == 0x00:
                # empty value
                self.readBytes(8)
                self.cells.append((typeId, None))
            elif typeId == 0x01:
                # number
                val = self.readDouble()
                self.cells.append((typeId, val))
            elif typeId == 0x02:
                # string
                pos = self.getCurrentPos()
                ret, length = globals.getUnicodeRichExtText(self.bytes[pos:])
                text = ret.baseText
                text = globals.encodeName(text)
                self.moveForward(length)
                self.cells.append((typeId, text))
            elif typeId == 0x04:
                # boolean
                val = self.readUnsignedInt(1)
                self.readBytes(7) # next 7 bytes not used
                self.cells.append((typeId, val))
            elif typeId == 0x10:
                # error value
                val = self.readUnsignedInt(1)
                self.readBytes(7) # next 7 bytes not used
                self.cells.append((typeId, val))
            else:
                globals.error("error parsing CRN record\n")
                sys.exit(1)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("first column: %d"%self.firstCol)
        self.appendLine("last column:  %d"%self.lastCol)
        self.appendLine("row index: %d"%self.rowIndex)

        for cell in self.cells:
            typeId, val = cell[0], cell[1]
            if typeId == 0x00:
                # empty value
                self.appendLine("* empty value")
            elif typeId == 0x01:
                # number
                self.appendLine("* numeric value (%g)"%val)
            elif typeId == 0x02:
                # string
                self.appendLine("* string value (%s)"%val)
            elif typeId == 0x04:
                # boolean
                self.appendLine("* boolean value (%d)"%val)
            elif typeId == 0x10:
                # error value
                self.appendLine("* error value (%d)"%val)
            else:
                error("error parsing CRN record\n")
                sys.exit(1)

    def fillModel (self, model):
        self.__parseBytes()
        sb = model.getWorkbookGlobal().getLastSupbook()
        # this must be an external document supbook.
        if sb.type != xlsmodel.Supbook.Type.External:
            return
        cache = sb.getCurrentSheetCache()
        for col in xrange(self.firstCol, self.lastCol+1):
            cell = self.cells[col-self.firstCol]
            typeId, val = cell[0], cell[1]
            cache.setValue(self.rowIndex, col, typeId, val)
            

class RefreshAll(BaseRecordHandler):

    def parseBytes (self):
        boolVal = globals.getSignedInt(self.bytes[0:2])
        strVal = "no"
        if boolVal:
            strVal = "yes"
        self.appendLine("refresh all external data ranges and pivot tables: %s"%strVal)


class Hyperlink(BaseRecordHandler):

    def parseBytes (self):
        rowFirst = self.readUnsignedInt(2)
        rowLast = self.readUnsignedInt(2)
        colFirst = self.readUnsignedInt(2)
        colLast = self.readUnsignedInt(2)
        # Rest of the stream stores undocumented hyperlink stream.  Refer to 
        # page 128 of MS Excel binary format spec.
        self.appendLine("rows: %d - %d"%(rowFirst, rowLast))
        self.appendLine("columns: %d - %d"%(colFirst, colLast))
        msg  = "NOTE: The stream after the first 8 bytes stores undocumented hyperlink stream.  "
        msg += "Refer to page 128 of the MS Excel binary format spec."
        self.appendLine('')
        self.appendMultiLine(msg)


class PhoneticInfo(BaseRecordHandler):

    phoneticType = [
        'narrow Katakana', # 0x00
        'wide Katakana',   # 0x01
        'Hiragana',        # 0x02
        'any type'         # 0x03
    ]

    @staticmethod
    def getPhoneticType (flag):
        return globals.getValueOrUnknown(PhoneticInfo.phoneticType, flag)

    alignType = [
        'general alignment',    # 0x00
        'left aligned',         # 0x01
        'center aligned',       # 0x02
        'distributed alignment' # 0x03
    ]

    @staticmethod
    def getAlignType (flag):
        return globals.getValueOrUnknown(PhoneticInfo.alignType, flag)

    def parseBytes (self):
        fontIdx = self.readUnsignedInt(2)
        self.appendLine("font ID: %d"%fontIdx)
        flags = self.readUnsignedInt(1)

        # flags: 0 0 0 0 0 0 0 0
        #       | unused| B | A |

        phType    = (flags)   & 0x03
        alignType = (flags/4) & 0x03

        self.appendLine("phonetic type: %s"%PhoneticInfo.getPhoneticType(phType))
        self.appendLine("alignment: %s"%PhoneticInfo.getAlignType(alignType))

        self.readUnsignedInt(1) # unused byte
        
        # TODO: read cell ranges.

        return


class Font(BaseRecordHandler):

    fontFamilyNames = [
        'not applicable', # 0x00
        'roman',          # 0x01
        'swiss',          # 0x02
        'modern',         # 0x03
        'script',         # 0x04
        'decorative'      # 0x05
    ]

    @staticmethod
    def getFontFamily (code):
        return globals.getValueOrUnknown(Font.fontFamilyNames, code)

    scriptNames = [
        'normal script',
        'superscript',
        'subscript'
    ]

    @staticmethod
    def getScriptName (code):
        return globals.getValueOrUnknown(Font.scriptNames, code)


    underlineTypes = {
        0x00: 'no underline',
        0x01: 'single underline',
        0x02: 'double underline',
        0x21: 'single accounting',
        0x22: 'double accounting'
    }

    @staticmethod
    def getUnderlineStyleName (val):
        return globals.getValueOrUnknown(Font.underlineTypes, val)

    charSetNames = {
        0x00: 'ANSI_CHARSET',
        0x01: 'DEFAULT_CHARSET',
        0x02: 'SYMBOL_CHARSET',
        0x4D: 'MAC_CHARSET',
        0x80: 'SHIFTJIS_CHARSET',
        0x81: 'HANGEUL_CHARSET',
        0x81: 'HANGUL_CHARSET',
        0x82: 'JOHAB_CHARSET',
        0x86: 'GB2312_CHARSET',
        0x88: 'CHINESEBIG5_CHARSET',
        0xA1: 'GREEK_CHARSET',
        0xA2: 'TURKISH_CHARSET',
        0xA3: 'VIETNAMESE_CHARSET',
        0xB1: 'HEBREW_CHARSET',
        0xB2: 'ARABIC_CHARSET',
        0xBA: 'BALTIC_CHARSET',
        0xCC: 'RUSSIAN_CHARSET',
        0xDD: 'THAI_CHARSET',
        0xEE: 'EASTEUROPE_CHARSET'
    }

    @staticmethod
    def getCharSetName (code):
        return globals.getValueOrUnknown(Font.charSetNames, code)

    def parseBytes (self):
        height     = self.readUnsignedInt(2)
        flags      = self.readUnsignedInt(2)
        colorId    = self.readUnsignedInt(2)

        boldStyle  = self.readUnsignedInt(2)
        boldStyleName = '(unknown)'
        if boldStyle == 400:
            boldStyleName = 'normal'
        elif boldStyle == 700:
            boldStyleName = 'bold'

        superSub   = self.readUnsignedInt(2)
        ulStyle    = self.readUnsignedInt(1)
        fontFamily = self.readUnsignedInt(1)
        charSet    = self.readUnsignedInt(1)
        reserved   = self.readUnsignedInt(1)
        nameLen    = self.readUnsignedInt(1)
        fontName, nameLen = globals.getRichText(self.readRemainingBytes(), nameLen)
        self.appendLine("font height: %d"%height)
        self.appendLine("color ID: %d"%colorId)
        self.appendLine("bold style: %s (%d)"%(boldStyleName, boldStyle))
        self.appendLine("script type: %s"%Font.getScriptName(superSub))
        self.appendLine("underline type: %s"%Font.getUnderlineStyleName(ulStyle))
        self.appendLine("character set: %s"%Font.getCharSetName(charSet))
        self.appendLine("font family: %s"%Font.getFontFamily(fontFamily))
        self.appendLine("font name: %s (%d)"%(fontName, nameLen))


class XF(BaseRecordHandler):

    horAlignTypes = [
        '',                                  #            0x00
        'left alignment',                    # ALCLEFT    0x01   
        'centered alignment',                # ALCCTR     0x02  
        'right alignment',                   # ALCRIGHT   0x03  
        'fill alignment',                    # ALCFILL    0x04  
        'justify alignment',                 # ALCJUST    0x05  
        'center-across-selection alignment', # ALCCONTCTR 0x06  
        'distributed alignment',             # ALCDIST    0x07  
        'alignment not specified'            # ALCNIL     0xFF  
    ]

    vertAlignTypes = [
        'top alignment',        # ALCVTOP  0x00
        'center alignment',     # ALCVCTR  0x01
        'bottom alignment',     # ALCVBOT  0x02
        'justify alignment',    # ALCVJUST 0x03
        'distributed alignment' # ALCVDIST 0x04
    ]

    readOrderTypes = [
        'context',       # READING_ORDER_CONTEXT 0x00
        'left-to-right', # READING_ORDER_LTR     0x01
        'right-to-left'  # READING_ORDER_RTL     0x02
    ]

    borderStyles = [
        ['NONE','No border'],                             # 0x0000
        ['THIN','Thin line'],                             # 0x0001
        ['MEDIUM','Medium line'],                         # 0x0002
        ['DASHED','Dashed line'],                         # 0x0003
        ['DOTTED','Dotted line'],                         # 0x0004
        ['THICK','Thick line'],                           # 0x0005
        ['DOUBLE','Double line'],                         # 0x0006
        ['HAIR','Hairline'],                              # 0x0007
        ['MEDIUMDASHED','Medium dashed line'],            # 0x0008
        ['DASHDOT','Dash-dot line'],                      # 0x0009
        ['MEDIUMDASHDOT','Medium dash-dot line'],         # 0x000A
        ['DASHDOTDOT','Dash-dot-dot line'],               # 0x000B
        ['MEDIUMDASHDOTDOT','Medium dash-dot-dot line'],  # 0x000C
        ['SLANTDASHDOT','Slanted dash-dot-dot line']      # 0x000D
    ]

    @staticmethod
    def printBorderStyle (val):
        if val >= len(XF.borderStyles):
            return '(unknown)'

        return "%s - %s (0x%2.2X)"%(XF.borderStyles[val][0], XF.borderStyles[val][1], val)

    class XFBase(object):
        def __init__ (self):
            pass

        def parseHeaderBytes (self, strm):
            byte = strm.readUnsignedInt(1)
            self.horAlign = (byte & 0x07)
            self.wrapText = (byte & 0x08) != 0
            self.verAlign = (byte & 0x70) / (2**4)
            self.distributed = (byte & 0x80) != 0
            self.textRotation = strm.readUnsignedInt(1)
            byte = strm.readUnsignedInt(1)
            self.indentLevel = (byte & 0x0F)
            self.shrinkToFit = (byte & 0x10) != 0
            self.readOrder   = (byte & 0xC0) / (2**6)

        def parseBorderStyles (self, strm):
            byte = strm.readUnsignedInt(1)
            self.leftBdrStyle   = (byte & 0x0F)
            self.rightBdrStyle  = (byte & 0xF0) / (2**4)
            byte = strm.readUnsignedInt(1)
            self.topBdrStyle    = (byte & 0x0F)
            self.bottomBdrStyle = (byte & 0xF0) / (2**4)

    class CellXF(XFBase):
        def __init__ (self):
            pass

        def parseBytes (self, strm):
            self.parseHeaderBytes(strm)
            byte = strm.readUnsignedInt(1)
            self.atrNum  = (byte & 0x04) != 0
            self.atrFnt  = (byte & 0x08) != 0
            self.atrAlc  = (byte & 0x10) != 0
            self.atrBdr  = (byte & 0x20) != 0
            self.atrPat  = (byte & 0x40) != 0
            self.atrProt = (byte & 0x80) != 0
            self.parseBorderStyles(strm)

    class CellStyleXF(XFBase):
        def __init__ (self):
            pass

        def parseBytes (self, strm):
            self.parseHeaderBytes(strm)
            strm.readUnsignedInt(1) # skip 1 byte.
            self.parseBorderStyles(strm)
            byte = strm.readUnsignedInt(2)
            self.leftColor  = (byte & 0x007F)           # 7-bits
            self.rightColor = (byte & 0x0780) / (2**7)  # 7-bits
            self.diagBorder = (byte & 0xC000) / (2**14) # 2-bits


    def __parseBytes (self):
        self.fontId = self.readUnsignedInt(2)
        self.numId = self.readUnsignedInt(2)
        flags = self.readUnsignedInt(2)
        self.locked = (flags & 0x0001) != 0
        self.hidden = (flags & 0x0002) != 0
        self.style  = (flags & 0x0004) != 0
        self.prefix = (flags & 0x0008) != 0

        # ID of cell style XF record which it inherits styles from.  Should be
        # 0xFFF it the style flag is on.
        self.cellStyleXFIndex = (flags & 0xFFF0) / (2**4)

        if self.style:
            self.data = XF.CellStyleXF()
            self.data.parseBytes(self)
        else:
            self.data = XF.CellXF()
            self.data.parseBytes(self)


    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("font ID: %d"%self.fontId)
        self.appendLine("number format ID: %d"%self.numId)
        self.appendLineBoolean("locked protection", self.locked)
        self.appendLineBoolean("hidden protection", self.hidden)
        self.appendLineBoolean("prefix characters present", self.prefix)

        s = "cell XF"
        if self.style:
            s = "cell style XF"
        self.appendLine("stored data type: " + s)

        # common data between cell XF and cell style XF

        # Horizontal alignment
        horAlignName = globals.getValueOrUnknown(
            XF.horAlignTypes[:-1], self.data.horAlign, 'not specified')
        self.appendLine("horizontal alignment: %s (0x%2.2X)"%(horAlignName, self.data.horAlign))
        self.appendLineBoolean("distributed", self.data.distributed)

        self.appendLineBoolean("wrap text", self.data.wrapText)

        # Vertical alignment
        verAlignName = globals.getValueOrUnknown(
            XF.vertAlignTypes, self.data.verAlign, 'unknown')
        self.appendLine("vertical alignment: %s (0x%2.2X)"%(verAlignName, self.data.verAlign))

        # Text rotation
        s = "text rotation: "
        if self.data.textRotation == 0xFF:
            s += "vertical"
        elif self.data.textRotation >= 0 and self.data.textRotation <= 90:
            s += "%d degrees (counterclockwise)"%self.data.textRotation
        elif self.data.textRotation > 90 and self.data.textRotation <= 180:
            s += "%d degrees (clockwise)"%(self.data.textRotation - 90)
        self.appendLine(s)

        self.appendLine("indent level: %d"%self.data.indentLevel)
        self.appendLineBoolean("shrink to fit", self.data.shrinkToFit)
        self.appendLine("reading order: %s"%globals.getValueOrUnknown(XF.readOrderTypes, self.data.readOrder))

        self.appendLine("border style (l): %s"%XF.printBorderStyle(self.data.leftBdrStyle))
        self.appendLine("border style (r): %s"%XF.printBorderStyle(self.data.rightBdrStyle))
        self.appendLine("border style (t): %s"%XF.printBorderStyle(self.data.topBdrStyle))
        self.appendLine("border style (b): %s"%XF.printBorderStyle(self.data.bottomBdrStyle))

        if self.style:
            # cell style XF data
            pass
        else:
            # cell XF data
            pass


class FeatureHeader(BaseRecordHandler):

    def parseBytes (self):
        recordType = self.readUnsignedInt(2)
        frtFlag = self.readUnsignedInt(2) # currently 0
        self.readBytes(8) # reserved (currently all 0)
        featureTypeId = self.readUnsignedInt(2)
        featureTypeText = 'unknown'
        if featureTypeId == 2:
            featureTypeText = 'enhanced protection'
        elif featureTypeId == 4:
            featureTypeText = 'smart tag'
        featureHdr = self.readUnsignedInt(1) # must be 1
        sizeHdrData = self.readSignedInt(4)
        sizeHdrDataText = 'byte size'
        if sizeHdrData == -1:
            sizeHdrDataText = 'size depends on feature type'

        self.appendLine("record type: 0x%4.4X (must match the header)"%recordType)
        self.appendLine("feature type: %d (%s)"%(featureTypeId, featureTypeText))
        self.appendLine("size of header data: %d (%s)"%(sizeHdrData, sizeHdrDataText))

        if featureTypeId == 2 and sizeHdrData == -1:
            # enhanced protection optionsss
            flags = self.readUnsignedInt(4)
            self.appendLine("enhanced protection flag: 0x%8.8X"%flags)

            optEditObj             = (flags & 0x00000001)
            optEditScenario        = (flags & 0x00000002)
            optFormatCells         = (flags & 0x00000004)
            optFormatColumns       = (flags & 0x00000008)
            optFormatRows          = (flags & 0x00000010)
            optInsertColumns       = (flags & 0x00000020)
            optInsertRows          = (flags & 0x00000040)
            optInsertLinks         = (flags & 0x00000080)
            optDeleteColumns       = (flags & 0x00000100)
            optDeleteRows          = (flags & 0x00000200)
            optSelectLockedCells   = (flags & 0x00000400)
            optSort                = (flags & 0x00000800)
            optUseAutofilter       = (flags & 0x00001000)
            optUsePivotReports     = (flags & 0x00002000)
            optSelectUnlockedCells = (flags & 0x00004000)
            self.appendLine("  edit object:             %s"%self.getEnabledDisabled(optEditObj))
            self.appendLine("  edit scenario:           %s"%self.getEnabledDisabled(optEditScenario))
            self.appendLine("  format cells:            %s"%self.getEnabledDisabled(optFormatCells))
            self.appendLine("  format columns:          %s"%self.getEnabledDisabled(optFormatColumns))
            self.appendLine("  format rows:             %s"%self.getEnabledDisabled(optFormatRows))
            self.appendLine("  insert columns:          %s"%self.getEnabledDisabled(optInsertColumns))
            self.appendLine("  insert rows:             %s"%self.getEnabledDisabled(optInsertRows))
            self.appendLine("  insert hyperlinks:       %s"%self.getEnabledDisabled(optInsertLinks))
            self.appendLine("  delete columns:          %s"%self.getEnabledDisabled(optDeleteColumns))
            self.appendLine("  delete rows:             %s"%self.getEnabledDisabled(optDeleteRows))
            self.appendLine("  select locked cells:     %s"%self.getEnabledDisabled(optSelectLockedCells))
            self.appendLine("  sort:                    %s"%self.getEnabledDisabled(optSort))
            self.appendLine("  use autofilter:          %s"%self.getEnabledDisabled(optUseAutofilter))
            self.appendLine("  use pivot table reports: %s"%self.getEnabledDisabled(optUsePivotReports))
            self.appendLine("  select unlocked cells:   %s"%self.getEnabledDisabled(optSelectUnlockedCells))

        return

# -------------------------------------------------------------------
# SX - Pivot Table

class DConName(BaseRecordHandler):

    def __parseBytes (self):
        self.rangeName = self.readUnicodeString()
        self.flag = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("defined name: %s"%self.rangeName)
        if self.flag == 0:
            self.appendMultiLine("This defined name has a workbook scope and is contained in this file.")
        else:
            # The additional bytes contain info about the workbook and
            # worksheet where the defined name is located.  We don't handle
            # this yet.
            pass

class DConRef(BaseRecordHandler):

    def __parseBytes (self):
        self.ref = RefU(self)
        textLen = self.readUnsignedInt(2)
        bytes = self.bytes[self.pos:]
        text, byteLen = globals.getRichText(bytes, textLen)
        self.sheetName = globals.encodeName(text)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("range: %s"%self.ref.toString())
        self.appendLine("sheet name: %s"%self.sheetName)

class SXIvd(BaseRecordHandler):

    def __parseBytes (self):
        self.ids = []
        n = self.getSize() / 2
        for i in xrange(0, n):
            self.ids.append(self.readSignedInt(2))

    def parseBytes (self):
        self.__parseBytes()
        for id in self.ids:
            self.appendLine("field value: %d"%id)

class SXViewEx9(BaseRecordHandler):

    def parseBytes (self):
        rt = self.readUnsignedInt(2)
        dummy = self.readBytes(6)
        flags = self.readUnsignedInt(4)
        autoFmtId = self.readUnsignedInt(2)

        self.appendLine("record type: %4.4Xh (always 0x0810)"%rt)
        self.appendLine("autoformat index: %d"%autoFmtId)

        nameLen = self.readSignedInt(2)
        if nameLen > 0:
            name, nameLen = globals.getRichText(self.readRemainingBytes(), nameLen)
            self.appendLine("grand total name: %s"%name)
        else:
            self.appendLine("grand total name: (none)")
        return


class SXAddlInfo(BaseRecordHandler):

    sxcNameList = {
        0x00: "sxcView",
        0x01: "sxcField",
        0x02: "sxcHierarchy",
        0x03: "sxcCache",
        0x04: "sxcCacheField",
        0x05: "sxcQsi",
        0x06: "sxcQuery",
        0x07: "sxcGrpLevel",
        0x08: "sxcGroup"
    }

    sxdNameList = {
        0x00: 'sxdId',
        0x01: 'sxdVerUpdInv',
        0x02: 'sxdVer10Info',
        0x03: 'sxdCalcMember',
        0x04: 'sxdXMLSource',
        0x05: 'sxdProperty',
        0x05: 'sxdSrcDataFile',
        0x06: 'sxdGrpLevelInfo',
        0x06: 'sxdSrcConnFile',
        0x07: 'sxdGrpInfo',
        0x07: 'sxdReconnCond',
        0x08: 'sxdMember',
        0x09: 'sxdFilterMember',
        0x0A: 'sxdCalcMemString',
        0xFF: 'sxdEnd'
    }

    def parseBytes (self):
        dummy = self.readBytes(2) # 0x0864
        dummy = self.readBytes(2) # 0x0000
        sxc = self.readBytes(1)[0]
        sxd = self.readBytes(1)[0]
        dwUserData = self.readBytes(4)
        dummy = self.readBytes(2)

        className = "(unknown)"
        if SXAddlInfo.sxcNameList.has_key(sxc):
            className = SXAddlInfo.sxcNameList[sxc]
        self.appendLine("class name: %s"%className)
        typeName = '(unknown)'
        if SXAddlInfo.sxdNameList.has_key(sxd):
            typeName = SXAddlInfo.sxdNameList[sxd]
        self.appendLine("type name: %s"%typeName)
        
        if sxd == 0x00:
            self.__parseId(sxc, dwUserData)

        elif sxd == 0x02:
            if sxc == 0x03:
                self.__parseSxDbSave10()
            elif sxc == 0x00:
                self.__parseViewFlags(dwUserData)

    def __parseViewFlags (self, dwUserData):
        flags = globals.getUnsignedInt(dwUserData)
        viewVer = (flags & 0x000000FF)
        verName = self.__getExcelVerName(viewVer)
        self.appendLine("PivotTable view version: %s"%verName)
        displayImmediateItems = (flags & 0x00000100)
        enableDataEd          = (flags & 0x00000200)
        disableFList          = (flags & 0x00000400)
        reenterOnLoadOnce     = (flags & 0x00000800)
        notViewCalcMembers    = (flags & 0x00001000)
        notVisualTotals       = (flags & 0x00002000)
        pageMultiItemLabel    = (flags & 0x00004000)
        tensorFillCv          = (flags & 0x00008000)
        hideDDData            = (flags & 0x00010000)

        self.appendLine("display immediate items: %s"%self.getYesNo(displayImmediateItems))
        self.appendLine("editing values in data area allowed: %s"%self.getYesNo(enableDataEd))
        self.appendLine("field list disabled: %s"%self.getYesNo(disableFList))
        self.appendLine("re-center on load once: %s"%self.getYesNo(reenterOnLoadOnce))
        self.appendLine("hide calculated members: %s"%self.getYesNo(notViewCalcMembers))
        self.appendLine("totals include hidden members: %s"%self.getYesNo(notVisualTotals))
        self.appendLine("(Multiple Items) instead of (All) in page field: %s"%self.getYesNo(pageMultiItemLabel))
        self.appendLine("background color from source: %s"%self.getYesNo(tensorFillCv))
        self.appendLine("hide drill-down for data field: %s"%self.getYesNo(hideDDData))

    def __parseId (self, sxc, dwUserData):
        if sxc == 0x03:
            idCache = globals.getUnsignedInt(dwUserData)
            self.appendLine("cache ID: %d"%idCache)
        elif sxc in [0x00, 0x01, 0x02, 0x05, 0x06, 0x07, 0x08]:
            lenStr = globals.getUnsignedInt(dwUserData)
            self.appendLine("length of ID string: %d"%lenStr)
            textLen = globals.getUnsignedInt(self.readBytes(2))
            data = self.bytes[self.getCurrentPos():]
            if lenStr == 0:
                self.appendLine("name (ID) string: (continued from last record)")
            elif lenStr == len(data) - 1:
                text, textLen = globals.getRichText(data, textLen)
                self.appendLine("name (ID) string: %s"%text)
            else:
                self.appendLine("name (ID) string: (first of multiple records)")


    def __parseSxDbSave10 (self):
        countGhostMax = globals.getSignedInt(self.readBytes(4))
        self.appendLine("max ghost pivot items: %d"%countGhostMax)

        # version last refreshed this cache
        lastVer = globals.getUnsignedInt(self.readBytes(1))
        verName = self.__getExcelVerName(lastVer)
        self.appendLine("last version refreshed: %s"%verName)
        
        # minimum version needed to refresh this cache
        lastVer = globals.getUnsignedInt(self.readBytes(1))
        verName = self.__getExcelVerName(lastVer)
        self.appendLine("minimum version needed to refresh: %s"%verName)

        # date last refreshed
        dateRefreshed = globals.getDouble(self.readBytes(8))
        self.appendLine("date last refreshed: %g"%dateRefreshed)


    def __getExcelVerName (self, ver):
        verName = '(unknown)'
        if ver == 0:
            verName = 'Excel 9 (2000) and earlier'
        elif ver == 1:
            verName = 'Excel 10 (XP)'
        elif ver == 2:
            verName = 'Excel 11 (2003)'
        elif ver == 3:
            verName = 'Excel 12 (2007)'
        return verName


class SXDb(BaseRecordHandler):

    def parseBytes (self):
        recCount = self.readUnsignedInt(4)
        strmId   = self.readUnsignedInt(2)
        flags    = self.readUnsignedInt(2)
        self.appendLine("number of records in database: %d"%recCount)
        self.appendLine("stream ID: %4.4Xh"%strmId)
#       self.appendLine("flags: %4.4Xh"%flags)

        saveLayout    = (flags & 0x0001)
        invalid       = (flags & 0x0002)
        refreshOnLoad = (flags & 0x0004)
        optimizeCache = (flags & 0x0008)
        backQuery     = (flags & 0x0010)
        enableRefresh = (flags & 0x0020)
        self.appendLine("save data with table layout: %s"%self.getYesNo(saveLayout))
        self.appendLine("invalid table (must be refreshed before next update): %s"%self.getYesNo(invalid))
        self.appendLine("refresh table on load: %s"%self.getYesNo(refreshOnLoad))
        self.appendLine("optimize cache for least memory use: %s"%self.getYesNo(optimizeCache))
        self.appendLine("query results obtained in the background: %s"%self.getYesNo(backQuery))
        self.appendLine("refresh is enabled: %s"%self.getYesNo(enableRefresh))

        dbBlockRecs = self.readUnsignedInt(2)
        baseFields = self.readUnsignedInt(2)
        allFields = self.readUnsignedInt(2)
        self.appendLine("number of records for each database block: %d"%dbBlockRecs)
        self.appendLine("number of base fields: %d"%baseFields)
        self.appendLine("number of all fields: %d"%allFields)

        dummy = self.readBytes(2)
        type = self.readUnsignedInt(2)
        typeName = '(unknown)'
        if type == 1:
            typeName = 'Excel worksheet'
        elif type == 2:
            typeName = 'External data'
        elif type == 4:
            typeName = 'Consolidation'
        elif type == 8:
            typeName = 'Scenario PivotTable'
        self.appendLine("type: %s (%d)"%(typeName, type))
        textLen = self.readUnsignedInt(2)
        changedBy, textLen = globals.getRichText(self.readRemainingBytes(), textLen)
        self.appendLine("changed by: %s"%changedBy)


class SXDbEx(BaseRecordHandler):

    def parseBytes (self):
        lastChanged = self.readDouble()
        sxFmlaRecs = self.readUnsignedInt(4)
        self.appendLine("last changed: %g"%lastChanged)
        self.appendLine("count of SXFORMULA records for this cache: %d"%sxFmlaRecs)


class SXField(BaseRecordHandler):

    dataTypeNames = {
        0x0000: 'spc',
        0x0480: 'str',
        0x0520: 'int[+dbl]',
        0x0560: 'dbl',
        0x05A0: 'str+int[+dbl]',
        0x05E0: 'str+dbl',
        0x0900: 'dat',
        0x0D00: 'dat+int/dbl',
        0x0D80: 'dat+str[+int/dbl]'
    }

    def parseBytes (self):
        flags = self.readUnsignedInt(2)
        origItems  = (flags & 0x0001)
        postponed  = (flags & 0x0002)
        calculated = (flags & 0x0004)
        groupChild = (flags & 0x0008)
        numGroup   = (flags & 0x0010)
        longIndex  = (flags & 0x0200)
        self.appendLine("original items: %s"%self.getYesNo(origItems))
        self.appendLine("postponed: %s"%self.getYesNo(postponed))
        self.appendLine("calculated: %s"%self.getYesNo(calculated))
        self.appendLine("group child: %s"%self.getYesNo(groupChild))
        self.appendLine("num group: %s"%self.getYesNo(numGroup))
        self.appendLine("long index: %s"%self.getYesNo(longIndex))
        dataType = (flags & 0x0DE0)
        if SXField.dataTypeNames.has_key(dataType):
            self.appendLine("data type: %s (%4.4Xh)"%(SXField.dataTypeNames[dataType], dataType))
        else:
            self.appendLine("data type: unknown (%4.4Xh)"%dataType)

        grpSubField = self.readUnsignedInt(2)
        grpBaseField = self.readUnsignedInt(2)
        itemCount = self.readUnsignedInt(2)
        grpItemCount = self.readUnsignedInt(2)
        baseItemCount = self.readUnsignedInt(2)
        srcItemCount = self.readUnsignedInt(2)
        self.appendLine("group sub-field: %d"%grpSubField)
        self.appendLine("group base-field: %d"%grpBaseField)
        self.appendLine("item count: %d"%itemCount)
        self.appendLine("group item count: %d"%grpItemCount)
        self.appendLine("base item count: %d"%baseItemCount)
        self.appendLine("source item count: %d"%srcItemCount)

        # field name
        textLen = self.readUnsignedInt(2)
        name, textLen = globals.getRichText(self.readRemainingBytes(), textLen)
        self.appendLine("field name: %s"%name)


class SXStreamID(BaseRecordHandler):

    def parseBytes (self):
        if self.size != 2:
            return

        strmId = globals.getSignedInt(self.bytes)
        self.strmData.appendPivotCacheId(strmId)
        self.appendLine("pivot cache stream ID in SX DB storage: %4.4X"%strmId)


class SXView(BaseRecordHandler):

    def parseBytes (self):
        rowFirst = self.readUnsignedInt(2)
        rowLast  = self.readUnsignedInt(2)
        self.appendLine("row range: %d - %d"%(rowFirst, rowLast))

        colFirst = self.readUnsignedInt(2)
        colLast  = self.readUnsignedInt(2)
        self.appendLine("col range: %d - %d"%(colFirst,colLast))

        rowHeadFirst = self.readUnsignedInt(2)
        rowDataFirst = self.readUnsignedInt(2)
        colDataFirst = self.readUnsignedInt(2)
        self.appendLine("heading row: %d"%rowHeadFirst)
        self.appendLine("data row: %d"%rowDataFirst)
        self.appendLine("data col: %d"%colDataFirst)

        cacheIndex = self.readUnsignedInt(2)
        self.appendLine("cache index: %d"%cacheIndex)

        self.readBytes(2)

        dataFieldAxis = self.readUnsignedInt(2)
        self.appendLine("default data field axis: %d"%dataFieldAxis)

        dataFieldPos = self.readUnsignedInt(2)
        self.appendLine("default data field pos: %d"%dataFieldPos)

        numFields = self.readUnsignedInt(2)
        numRowFields = self.readUnsignedInt(2)
        numColFields = self.readUnsignedInt(2)
        numPageFields = self.readUnsignedInt(2)
        numDataFields = self.readUnsignedInt(2)
        numDataRows = self.readUnsignedInt(2)
        numDataCols = self.readUnsignedInt(2)
        self.appendLine("field count: %d"%numFields)
        self.appendLine("row field count: %d"%numRowFields)
        self.appendLine("col field count: %d"%numColFields)
        self.appendLine("page field count: %d"%numPageFields)
        self.appendLine("data field count: %d"%numDataFields)
        self.appendLine("data row count: %d"%numDataRows)
        self.appendLine("data col count: %d"%numDataCols)

        # option flags (TODO: display these later.)
        flags = self.readUnsignedInt(2)

        # autoformat index
        autoFmtIndex = self.readUnsignedInt(2)
        self.appendLine("autoformat index: %d"%autoFmtIndex)

        nameLenTable = self.readUnsignedInt(2)
        nameLenDataField = self.readUnsignedInt(2)
        text, nameLenTable = globals.getRichText(self.readBytes(nameLenTable+1), nameLenTable)
        self.appendLine("PivotTable name: %s"%text)
        text, nameLenDataField = globals.getRichText(self.readBytes(nameLenDataField+1), nameLenDataField)
        self.appendLine("data field name: %s"%text)


class SXViewSource(BaseRecordHandler):

    def parseBytes (self):
        if self.size != 2:
            return

        src = globals.getSignedInt(self.bytes)
        srcType = 'unknown'
        if src == 0x01:
            srcType = 'internal range (followed by DConRef, DConName or DConBin)'
        elif src == 0x02:
            srcType = 'external data source (followed by DbQuery)'
        elif src == 0x04:
            srcType = 'multiple consolidation ranges (followed by SXTbl)'
        elif src == 0x10:
            srcType = 'scenario (temporary internal structure)'

        self.appendLine("data source type: %s"%srcType)


class SXViewFields(BaseRecordHandler):

    def parseBytes (self):
        axis          = globals.getSignedInt(self.readBytes(2))
        subtotalCount = globals.getSignedInt(self.readBytes(2))
        subtotalType  = globals.getSignedInt(self.readBytes(2))
        itemCount     = globals.getSignedInt(self.readBytes(2))
        nameLen       = globals.getSignedInt(self.readBytes(2))
        
        axisType = 'unknown'
        if axis == 0:
            axisType = 'no axis'
        elif axis == 1:
            axisType = 'row'
        elif axis == 2:
            axisType = 'column'
        elif axis == 4:
            axisType = 'page'
        elif axis == 8:
            axisType = 'data'

        subtotalTypeName = 'unknown'
        if subtotalType == 0x0000:
            subtotalTypeName = 'None'
        elif subtotalType == 0x0001:
            subtotalTypeName = 'Default'
        elif subtotalType == 0x0002:
            subtotalTypeName = 'Sum'
        elif subtotalType == 0x0004:
            subtotalTypeName = 'CountA'
        elif subtotalType == 0x0008:
            subtotalTypeName = 'Average'
        elif subtotalType == 0x0010:
            subtotalTypeName = 'Max'
        elif subtotalType == 0x0020:
            subtotalTypeName = 'Min'
        elif subtotalType == 0x0040:
            subtotalTypeName = 'Product'
        elif subtotalType == 0x0080:
            subtotalTypeName = 'Count'
        elif subtotalType == 0x0100:
            subtotalTypeName = 'Stdev'
        elif subtotalType == 0x0200:
            subtotalTypeName = 'StdevP'
        elif subtotalType == 0x0400:
            subtotalTypeName = 'Var'
        elif subtotalType == 0x0800:
            subtotalTypeName = 'VarP'

        self.appendLine("axis type: %s"%axisType)
        self.appendLine("number of subtotals: %d"%subtotalCount)
        self.appendLine("subtotal type: %s"%subtotalTypeName)
        self.appendLine("number of items: %d"%itemCount)

        if nameLen == -1:
            self.appendLine("name: null (use name in the cache)")
        else:
            name, nameLen = globals.getRichText(self.readRemainingBytes(), nameLen)
            self.appendLine("name: %s"%name)


class SXViewFieldsEx(BaseRecordHandler):

    def __parseBytes (self):
        flag = self.readUnsignedInt(2)
        self.showAllItems      = (flag & 0x0001) != 0 # A
        self.dragToRow         = (flag & 0x0002) != 0 # B
        self.dragToColumn      = (flag & 0x0004) != 0 # C
        self.dragToPage        = (flag & 0x0008) != 0 # D
        self.dragToHide        = (flag & 0x0010) != 0 # E
        self.disableDragToData = (flag & 0x0020) != 0 # F
        reserved               = (flag & 0x0040) != 0 # G
        self.serverBased       = (flag & 0x0080) != 0 # H
        reserved               = (flag & 0x0100) != 0 # I
        self.autoSort          = (flag & 0x0200) != 0 # J
        self.ascendSort        = (flag & 0x0400) != 0 # K
        self.autoShow          = (flag & 0x0800) != 0 # L
        self.topAutoShow       = (flag & 0x1000) != 0 # M
        self.calculatedField   = (flag & 0x2000) != 0 # N
        self.insertPageBreaks  = (flag & 0x4000) != 0 # O
        self.hideNewItems      = (flag & 0x8000) != 0 # P

        flag = self.readUnsignedInt(1)
        # skip the first 5 bits.
        self.outlineForm       = (flag & 0x20) != 0 # Q
        self.insertBlankRow    = (flag & 0x40) != 0 # R
        self.subtotalAtTop     = (flag & 0x80) != 0 # S

        # number of items to show in auto show mode.
        self.autoShowCount = self.readUnsignedInt(1)

        self.autoSortItem = self.readSignedInt(2)
        self.autoShowItem = self.readSignedInt(2)
        self.numberFormat = self.readUnsignedInt(2)

        nameLen = self.readUnsignedInt(2)
        self.subName = None
        if nameLen != 0xFFFF:
            self.readBytes(8) # ignored
            self.subName, byteLen = getRichText(self.readRemainingBytes(), nameLen)
        
    def parseBytes (self):
        self.__parseBytes()
        self.appendLineBoolean("show all items", self.showAllItems)
        self.appendLineBoolean("drag to row", self.dragToRow)
        self.appendLineBoolean("drag to column", self.dragToColumn)
        self.appendLineBoolean("drag to page", self.dragToPage)
        self.appendLineBoolean("drag to hide", self.dragToHide)
        self.appendLineBoolean("disable drag to data", self.disableDragToData)
        self.appendLineBoolean("server based", self.serverBased)
        self.appendLineBoolean("auto sort", self.autoSort)
        self.appendLineBoolean("ascending sort", self.ascendSort)
        self.appendLineBoolean("auto show", self.autoShow)
        self.appendLineBoolean("top auto show", self.topAutoShow)
        self.appendLineBoolean("calculated field", self.calculatedField)
        self.appendLineBoolean("insert page breaks", self.insertPageBreaks)
        self.appendLineBoolean("hide new items after refresh", self.hideNewItems)

        self.appendLineBoolean("outline form", self.outlineForm)
        self.appendLineBoolean("insert blank row", self.insertBlankRow)
        self.appendLineBoolean("subtotal at top", self.subtotalAtTop)

        self.appendLine("items to show in auto show: %d"%self.autoShowCount)

        if self.autoSort:
            if self.autoSortItem == -1:
                self.appendLine("auto sort: sort by pivot items themselves")
            else:
                self.appendLine("auto sort: sort by data item %d"%self.autoSortItem)

        if self.autoShow:
            if self.autoShowItem == -1:
                self.appendLine("auto show: not enabled")
            else:
                self.appendLine("auto show: use data item %d"%self.autoShowItem)

        self.appendLine("number format: %d"%self.numberFormat)

        if self.subName == None:
            self.appendLine("aggregate function: none")
        else:
            self.appendLine("aggregate function: %s"%self.subName)


class SXDataItem(BaseRecordHandler):

    functionType = {
        0x00: 'sum',
        0x01: 'count',
        0x02: 'average',
        0x03: 'max',
        0x04: 'min',
        0x05: 'product',
        0x06: 'count nums',
        0x07: 'stddev',
        0x08: 'stddevp',
        0x09: 'var',
        0x0A: 'varp'
    }

    displayFormat = {
        0x00: 'normal',
        0x01: 'difference from',
        0x02: 'percentage of',
        0x03: 'perdentage difference from',
        0x04: 'running total in',
        0x05: 'percentage of row',
        0x06: 'percentage of column',
        0x07: 'percentage of total',
        0x08: 'index'
    }

    def parseBytes (self):
        isxvdData = self.readUnsignedInt(2)
        funcIndex = self.readUnsignedInt(2)

        # data display format
        df = self.readUnsignedInt(2)

        # index to the SXVD/SXVI records used by the data display format
        sxvdIndex = self.readUnsignedInt(2)
        sxviIndex = self.readUnsignedInt(2)

        # index to the format table for this item
        fmtIndex = self.readUnsignedInt(2)

        # name
        nameLen = self.readSignedInt(2)
        name, nameLen = globals.getRichText(self.readRemainingBytes(), nameLen)

        self.appendLine("field that this data item is based on: %d"%isxvdData)
        funcName = '(unknown)'
        if SXDataItem.functionType.has_key(funcIndex):
            funcName = SXDataItem.functionType[funcIndex]
        self.appendLine("aggregate function: %s"%funcName)
        dfName = '(unknown)'
        if SXDataItem.displayFormat.has_key(df):
            dfName = SXDataItem.displayFormat[df]
        self.appendLine("data display format: %s"%dfName)
        self.appendLine("SXVD record index: %d"%sxvdIndex)
        self.appendLine("SXVI record index: %d"%sxviIndex)
        self.appendLine("format table index: %d"%fmtIndex)

        if nameLen == -1:
            self.appendLine("name: null (use name in the cache)")
        else:
            self.appendLine("name: %s"%name)

        return


class SXViewItem(BaseRecordHandler):

    itemTypes = {
        0xFE: 'Page',
        0xFF: 'Null',
        0x00: 'Data',
        0x01: 'Default',
        0x02: 'SUM',
        0x03: 'COUNTA',
        0x04: 'COUNT',
        0x05: 'AVERAGE',
        0x06: 'MAX',
        0x07: 'MIN',
        0x08: 'PRODUCT',
        0x09: 'STDEV',
        0x0A: 'STDEVP',
        0x0B: 'VAR',
        0x0C: 'VARP',
        0x0D: 'Grand total',
        0x0E: 'blank'
    }

    def parseBytes (self):
        itemType = self.readSignedInt(2)
        grbit    = self.readSignedInt(2)
        iCache   = self.readSignedInt(2)
        nameLen  = self.readSignedInt(2)
        
        itemTypeName = 'unknown'
        if SXViewItem.itemTypes.has_key(itemType):
            itemTypeName = SXViewItem.itemTypes[itemType]

        flags = ''
        if (grbit & 0x0001):
            flags += 'hidden, '
        if (grbit & 0x0002):
            flags += 'detail hidden, '
        if (grbit & 0x0008):
            flags += 'formula, '
        if (grbit & 0x0010):
            flags += 'missing, '

        if len(flags) > 0:
            # strip the trailing ', '
            flags = flags[:-2]
        else:
            flags = '(none)'

        self.appendLine("item type: %s"%itemTypeName)
        self.appendLine("flags: %s"%flags)
        self.appendLine("pivot cache index: %d"%iCache)
        if nameLen == -1:
            self.appendLine("name: null (use name in the cache)")
        else:
            name, nameLen = globals.getRichText(self.readRemainingBytes(), nameLen)
            self.appendLine("name: %s"%name)


class PivotQueryTableEx(BaseRecordHandler):
    """QSISXTAG: Pivot Table and Query Table Extensions (802h)"""
    excelVersionList = [
        'Excel 2000',
        'Excel XP',
        'Excel 2003',
        'Excel 2007'
    ]

    class TableType:
        QueryTable = 0
        PivotTable = 1

    def getExcelVersion (self, lastExcelVer):
        s = '(unknown)'
        if lastExcelVer < len(PivotQueryTableEx.excelVersionList):
            s = PivotQueryTableEx.excelVersionList[lastExcelVer]
        return s

    def parseBytes (self):
        recordType = self.readUnsignedInt(2)
        self.appendLine("record type (always 0802h): %4.4Xh"%recordType)
        dummyFlags = self.readUnsignedInt(2)
        self.appendLine("flags (must be zero): %4.4Xh"%dummyFlags)
        tableType = self.readUnsignedInt(2)
        s = '(unknown)'
        if tableType == PivotQueryTableEx.TableType.QueryTable:
            s = 'query table'
        elif tableType == PivotQueryTableEx.TableType.PivotTable:
            s = 'pivot table'
        self.appendLine("this record is for: %s"%s)

        # general flags
        flags = self.readUnsignedInt(2)
        enableRefresh = (flags & 0x0001)
        invalid       = (flags & 0x0002)
        tensorEx      = (flags & 0x0004)
        s = '(unknown)'
        if enableRefresh:
            s = 'ignore'
        else:
            s = 'check'
        self.appendLine("check for SXDB or QSI for table refresh: %s"%s)
        self.appendLine("PivotTable cache is invalid: %s"%self.getYesNo(invalid))
        self.appendLine("This is an OLAP PivotTable report: %s"%self.getYesNo(tensorEx))

        # feature-specific options
        featureOptions = self.readUnsignedInt(4)
        if tableType == PivotQueryTableEx.TableType.QueryTable:
            # query table
            preserveFormat = (featureOptions & 0x00000001)
            autoFit        = (featureOptions & 0x00000002)
            self.appendLine("keep formatting applied by the user: %s"%self.getYesNo(preserveFormat))
            self.appendLine("auto-fit columns after refresh: %s"%self.getYesNo(autoFit))
        elif tableType == PivotQueryTableEx.TableType.PivotTable:
            # pivot table
            noStencil         = (featureOptions & 0x00000001)
            hideTotAnnotation = (featureOptions & 0x00000002)
            includeEmptyRow   = (featureOptions & 0x00000008)
            includeEmptyCol   = (featureOptions & 0x00000010)
            self.appendLine("no large drop zones if no data fields: %s"%self.getTrueFalse(noStencil))
            self.appendLine("no asterisk for the total in OLAP table: %s"%self.getTrueFalse(hideTotAnnotation))
            self.appendLine("retrieve and show empty rows from OLAP source: %s"%self.getTrueFalse(includeEmptyRow))
            self.appendLine("retrieve and show empty columns from OLAP source: %s"%self.getTrueFalse(includeEmptyCol))

        self.appendLine("table last refreshed by: %s"%
            self.getExcelVersion(self.readUnsignedInt(1)))

        self.appendLine("minimal version that can refresh: %s"%
            self.getExcelVersion(self.readUnsignedInt(1)))

        offsetBytes = self.readUnsignedInt(1)
        self.appendLine("offset from first FRT byte to first cchName byte: %d"%offsetBytes)

        self.appendLine("first version that created the table: %s"%
            self.getExcelVersion(self.readUnsignedInt(1)))

        textLen = self.readUnsignedInt(2)
        name, textLen = globals.getRichText(self.readRemainingBytes(), textLen)
        self.appendLine("table name: %s"%name)
        return


class SXDouble(BaseRecordHandler):
    def parseBytes (self):
        val = self.readDouble()
        self.appendLine("value: %g"%val)


class SXBoolean(BaseRecordHandler):
    def parseBytes (self):
        pass

class SXError(BaseRecordHandler):
    def parseBytes (self):
        pass


class SXInteger(BaseRecordHandler):
    def parseBytes (self):
        pass


class SXString(BaseRecordHandler):
    def parseBytes (self):
        textLen = self.readUnsignedInt(2)
        text, textLen = globals.getRichText(self.readRemainingBytes(), textLen)
        self.appendLine("value: %s"%text)

# -------------------------------------------------------------------
# CT - Change Tracking

class CTCellContent(BaseRecordHandler):
    
    EXC_CHTR_TYPE_MASK       = 0x0007
    EXC_CHTR_TYPE_FORMATMASK = 0xFF00
    EXC_CHTR_TYPE_EMPTY      = 0x0000
    EXC_CHTR_TYPE_RK         = 0x0001
    EXC_CHTR_TYPE_DOUBLE     = 0x0002
    EXC_CHTR_TYPE_STRING     = 0x0003
    EXC_CHTR_TYPE_BOOL       = 0x0004
    EXC_CHTR_TYPE_FORMULA    = 0x0005

    def parseBytes (self):
        size = globals.getSignedInt(self.readBytes(4))
        id = globals.getSignedInt(self.readBytes(4))
        opcode = globals.getSignedInt(self.readBytes(2))
        accept = globals.getSignedInt(self.readBytes(2))
        tabCreateId = globals.getSignedInt(self.readBytes(2))
        valueType = globals.getSignedInt(self.readBytes(2))
        self.appendLine("header: (size=%d; index=%d; opcode=0x%2.2X; accept=%d)"%(size, id, opcode, accept))
        self.appendLine("sheet creation id: %d"%tabCreateId)

        oldType = (valueType/(2*2*2) & CTCellContent.EXC_CHTR_TYPE_MASK)
        newType = (valueType & CTCellContent.EXC_CHTR_TYPE_MASK)
        self.appendLine("value type: (old=%4.4Xh; new=%4.4Xh)"%(oldType, newType))
        self.readBytes(2) # ignore next 2 bytes.

        row = globals.getSignedInt(self.readBytes(2))
        col = globals.getSignedInt(self.readBytes(2))
        cell = formula.CellAddress(col, row)
        self.appendLine("cell position: %s"%cell.getName())

        oldSize = globals.getSignedInt(self.readBytes(2))
        self.readBytes(4) # ignore 4 bytes.

        fmtType = (valueType & CTCellContent.EXC_CHTR_TYPE_FORMATMASK)
        if fmtType == 0x1100:
            self.readBytes(16)
        elif fmtType == 0x1300:
            self.readBytes(8)

        self.readCell(oldType, "old cell type")
        self.readCell(newType, "new cell type")

    def readCell (self, cellType, cellName):

        cellTypeText = 'unknown'

        if cellType == CTCellContent.EXC_CHTR_TYPE_FORMULA:
            cellTypeText, formulaBytes, formulaText = self.readFormula()
            self.appendLine("%s: %s"%(cellName, cellTypeText))
            self.appendLine("formula bytes: %s"%globals.getRawBytes(formulaBytes, True, False))
            self.appendLine("tokens: %s"%formulaText)
            return

        if cellType == CTCellContent.EXC_CHTR_TYPE_EMPTY:
            cellTypeText = 'empty'
        elif cellType == CTCellContent.EXC_CHTR_TYPE_RK:
            cellTypeText = self.readRK()
        elif cellType == CTCellContent.EXC_CHTR_TYPE_DOUBLE:
            cellTypeText = self.readDouble()
        elif cellType == CTCellContent.EXC_CHTR_TYPE_STRING:
            cellTypeText = self.readString()
        elif cellType == CTCellContent.EXC_CHTR_TYPE_BOOL:
            cellTypeText = self.readBool()
        elif cellType == CTCellContent.EXC_CHTR_TYPE_FORMULA:
            cellTypeText, formulaText = self.readFormula()

        self.appendLine("%s: %s"%(cellName, cellTypeText))

    def readRK (self):
        valRK = globals.getSignedInt(self.readBytes(4))
        return 'RK value'

    def readDouble (self):
        val = globals.getDouble(self.readBytes(4))
        return "value %f"%val

    def readString (self):
        size = globals.getSignedInt(self.readBytes(2))
        pos = self.getCurrentPos()
        name, byteLen = globals.getRichText(self.bytes[pos:], size)
        self.setCurrentPos(pos + byteLen)
        return "string '%s'"%name

    def readBool (self):
        bool = globals.getSignedInt(self.readBytes(2))
        return "bool (%d)"%bool

    def readFormula (self):
        size = globals.getSignedInt(self.readBytes(2))
        fmlaBytes = self.readBytes(size)
        o = formula.FormulaParser(self.header, fmlaBytes)
        o.parse()
        return "formula", fmlaBytes, o.getText()

# -------------------------------------------------------------------
# CH - Chart

class Chart(BaseRecordHandler):

    def parseBytes (self):
        x = globals.getSignedInt(self.bytes[0:4])
        y = globals.getSignedInt(self.bytes[4:8])
        w = globals.getSignedInt(self.bytes[8:12])
        h = globals.getSignedInt(self.bytes[12:16])
        self.appendLine("position: (x, y) = (%d, %d)"%(x, y))
        self.appendLine("size: (width, height) = (%d, %d)"%(w, h))
        
class DefaultText(BaseRecordHandler):

    __types = [
        'non-percent or non-value',
        'percent or value',
        'non-scalable font',
        'scalable font']

    def __parseBytes (self):
        self.id = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine(globals.getValueOrUnknown(DefaultText.__types, self.id))

class Text(BaseRecordHandler):

    __horAlign = { 1: 'left', 2: 'center', 3: 'right', 4: 'justify', 7: 'distributed' }
    __verAlign = { 1: 'top', 2: 'center', 3: 'bottom', 4: 'justify', 7: 'distributed' }
    __bkgMode = { 1: 'transparent', 2: 'opaque' }

    def __parseBytes (self):
        self.at = self.readUnsignedInt(1)
        self.vat = self.readUnsignedInt(1)
        self.bkgMode = self.readUnsignedInt(2)
        self.textColor = self.readLongRGB()
        self.x = self.readSignedInt(4)
        self.y = self.readSignedInt(4)
        self.dx = self.readSignedInt(4)
        self.dy = self.readSignedInt(4)

        flag = self.readUnsignedInt(2)
        self.autoColor        = (flag & 0x0001) != 0 # A
        self.showKey          = (flag & 0x0002) != 0 # B
        self.showValue        = (flag & 0x0004) != 0 # C 
        unused                = (flag & 0x0008) != 0 # D (unused)
        self.autoText         = (flag & 0x0010) != 0 # E
        self.generated        = (flag & 0x0020) != 0 # F
        self.deleted          = (flag & 0x0040) != 0 # G
        self.autoMode         = (flag & 0x0080) != 0 # H
        unused                = (flag & 0x0700) != 0 # I (unused)
        self.showLabelAndPerc = (flag & 0x0800) != 0 # J
        self.showPercent      = (flag & 0x1000) != 0 # K
        self.showBubbleSizes  = (flag & 0x2000) != 0 # L
        self.showLabel        = (flag & 0x4000) != 0 # M
        reserved              = (flag & 0x8000) != 0 # N (reserved)

        self.icvTextColor = self.readICV()

        flag = self.readUnsignedInt(2)
        self.dlp = (flag & 0x000F)
        self.readingOrder = (flag & 0xC000) / (2**14)
        self.trot = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("horizontal alignment: %s"%
            globals.getValueOrUnknown(Text.__horAlign, self.at))
        self.appendLine("vertical alignment: %s"%
            globals.getValueOrUnknown(Text.__verAlign, self.vat))
        self.appendLine("text background: %s"%
            globals.getValueOrUnknown(Text.__bkgMode, self.bkgMode))

        # TODO : handle the rest of the data.

class Series(BaseRecordHandler):

    DATE     = 0
    NUMERIC  = 1
    SEQUENCE = 2
    TEXT     = 3

    seriesTypes = ['date', 'numeric', 'sequence', 'text']

    @staticmethod
    def getSeriesType (idx):
        r = 'unknown'
        if idx < len(CHSeries.seriesTypes):
            r = CHSeries.seriesTypes[idx]
        return r

    def __parseBytes (self):
        self.catType     = self.readUnsignedInt(2)
        self.valType     = self.readUnsignedInt(2) # must be 1 (ignored)
        self.catCount    = self.readUnsignedInt(2)
        self.valCount    = self.readUnsignedInt(2)
        self.bubbleType  = self.readUnsignedInt(2) # must be 1 (ignored)
        self.bubbleCount = self.readUnsignedInt(2)

    def parseBytes (self):
        self.__parseBytes()
        s = "unknown"
        if self.catType == 1:
            s = "numeric"
        elif self.catType == 3:
            s = "text"
        self.appendLine("data type: %s"%s)
        self.appendLine("category or horizontal value count: %d"%self.catCount)
        self.appendLine("value or vertical value count: %d"%self.valCount)
        self.appendLine("bubble size value count: %d"%self.bubbleCount)

class CHAxis(BaseRecordHandler):

    axisTypeList = ['x-axis', 'y-axis', 'z-axis']

    def parseBytes (self):
        axisType = self.readUnsignedInt(2)
        x = self.readSignedInt(4)
        y = self.readSignedInt(4)
        w = self.readSignedInt(4)
        h = self.readSignedInt(4)
        if axisType < len(CHAxis.axisTypeList):
            self.appendLine("axis type: %s (%d)"%(CHAxis.axisTypeList[axisType], axisType))
        else:
            self.appendLine("axis type: unknown")
        self.appendLine("area: (x, y, w, h) = (%d, %d, %d, %d) [no longer used]"%(x, y, w, h))


class CHProperties(BaseRecordHandler):

    def parseBytes (self):
        flags = globals.getSignedInt(self.bytes[0:2])
        emptyFlags = globals.getSignedInt(self.bytes[2:4])

        manualSeries   = "false"
        showVisCells   = "false"
        noResize       = "false"
        manualPlotArea = "false"

        if (flags & 0x0001):
            manualSeries = "true"
        if (flags & 0x0002):
            showVisCells = "true"
        if (flags & 0x0004):
            noResize = "true"
        if (flags & 0x0008):
            manualPlotArea = "true"

        self.appendLine("manual series: %s"%manualSeries)
        self.appendLine("show only visible cells: %s"%showVisCells)
        self.appendLine("no resize: %s"%noResize)
        self.appendLine("manual plot area: %s"%manualPlotArea)

        emptyValues = "skip"
        if emptyFlags == 1:
            emptyValues = "plot as zero"
        elif emptyFlags == 2:
            emptyValues = "interpolate empty values"

        self.appendLine("empty value treatment: %s"%emptyValues)


class CHLabelRange(BaseRecordHandler):

    def parseBytes (self):
        axisCross = self.readUnsignedInt(2)
        freqLabel = self.readUnsignedInt(2)
        freqTick  = self.readUnsignedInt(2)
        self.appendLine("axis crossing: %d"%axisCross)
        self.appendLine("label frequency: %d"%freqLabel)
        self.appendLine("tick frequency: %d"%freqTick)

        flags     = self.readUnsignedInt(2)
        betweenCateg = (flags & 0x0001)
        maxCross     = (flags & 0x0002)
        reversed     = (flags & 0x0004)
        self.appendLineBoolean("axis between categories", betweenCateg)
        self.appendLineBoolean("other axis crosses at maximum", maxCross)
        self.appendLineBoolean("axis reversed", reversed)


class CHLegend(BaseRecordHandler):
    
    dockModeMap = {0: 'bottom', 1: 'corner', 2: 'top', 3: 'right', 4: 'left', 7: 'not docked'}
    spacingMap = ['close', 'medium', 'open']

    def getDockModeText (self, val):
        if CHLegend.dockModeMap.has_key(val):
            return CHLegend.dockModeMap[val]
        else:
            return '(unknown)'

    def getSpacingText (self, val):
        if val < len(CHLegend.spacingMap):
            return CHLegend.spacingMap[val]
        else:
            return '(unknown)'

    def parseBytes (self):
        x = self.readSignedInt(4)
        y = self.readSignedInt(4)
        w = self.readSignedInt(4)
        h = self.readSignedInt(4)
        dockMode = self.readUnsignedInt(1)
        spacing  = self.readUnsignedInt(1)
        flags    = self.readUnsignedInt(2)

        docked     = (flags & 0x0001)
        autoSeries = (flags & 0x0002)
        autoPosX   = (flags & 0x0004)
        autoPosY   = (flags & 0x0008)
        stacked    = (flags & 0x0010)
        dataTable  = (flags & 0x0020)

        self.appendLine("legend position: (x, y) = (%d, %d)"%(x,y))
        self.appendLine("legend size: width = %d, height = %d"%(w,h))
        self.appendLine("dock mode: %s"%self.getDockModeText(dockMode))
        self.appendLine("spacing: %s"%self.getSpacingText(spacing))
        self.appendLineBoolean("docked", docked)
        self.appendLineBoolean("auto series", autoSeries)
        self.appendLineBoolean("auto position x", autoPosX)
        self.appendLineBoolean("auto position y", autoPosY)
        self.appendLineBoolean("stacked", stacked)
        self.appendLineBoolean("data table", dataTable)

        self.appendLine("")
        self.appendMultiLine("NOTE: Position and size are in units of 1/4000 of chart's width or height.")


class CHValueRange(BaseRecordHandler):

    def parseBytes (self):
        minVal = globals.getDouble(self.readBytes(8))
        maxVal = globals.getDouble(self.readBytes(8))
        majorStep = globals.getDouble(self.readBytes(8))
        minorStep = globals.getDouble(self.readBytes(8))
        cross = globals.getDouble(self.readBytes(8))
        flags = globals.getSignedInt(self.readBytes(2))

        autoMin   = (flags & 0x0001)
        autoMax   = (flags & 0x0002)
        autoMajor = (flags & 0x0004)
        autoMinor = (flags & 0x0008)
        autoCross = (flags & 0x0010)
        logScale  = (flags & 0x0020)
        reversed  = (flags & 0x0040)
        maxCross  = (flags & 0x0080)
        bit8      = (flags & 0x0100)

        self.appendLine("min: %g (auto min: %s)"%(minVal, self.getYesNo(autoMin)))
        self.appendLine("max: %g (auto max: %s)"%(maxVal, self.getYesNo(autoMax)))
        self.appendLine("major step: %g (auto major: %s)"%
            (majorStep, self.getYesNo(autoMajor)))
        self.appendLine("minor step: %g (auto minor: %s)"%
            (minorStep, self.getYesNo(autoMinor)))
        self.appendLine("cross: %g (auto cross: %s) (max cross: %s)"%
            (cross, self.getYesNo(autoCross), self.getYesNo(maxCross)))
        self.appendLine("biff5 or above: %s"%self.getYesNo(bit8))


class CHBar(BaseRecordHandler):

    def parseBytes (self):
        overlap = globals.getSignedInt(self.readBytes(2))
        gap     = globals.getSignedInt(self.readBytes(2))
        flags   = globals.getUnsignedInt(self.readBytes(2))

        horizontal = (flags & 0x0001)
        stacked    = (flags & 0x0002)
        percent    = (flags & 0x0004)
        shadow     = (flags & 0x0008)

        self.appendLine("overlap width: %d"%overlap)
        self.appendLine("gap: %d"%gap)
        self.appendLine("horizontal: %s"%self.getYesNo(horizontal))
        self.appendLine("stacked: %s"%self.getYesNo(stacked))
        self.appendLine("percent: %s"%self.getYesNo(percent))
        self.appendLine("shadow: %s"%self.getYesNo(shadow))


class CHLine(BaseRecordHandler):

    def parseBytes (self):
        flags   = globals.getUnsignedInt(self.readBytes(2))
        stacked = (flags & 0x0001)
        percent = (flags & 0x0002)
        shadow  = (flags & 0x0004)

        self.appendLine("stacked: %s"%self.getYesNo(stacked))
        self.appendLine("percent: %s"%self.getYesNo(percent))
        self.appendLine("shadow: %s"%self.getYesNo(shadow))


class Brai(BaseRecordHandler):

    destTypes = [
        'series, legend entry, trendline name, or error bars name',
        'values or horizontal values',
        'categories or vertical values',
        'bubble size values of the series']

    linkTypes = [
        'auto-generated category name, series name, or bubble size',
        'text or value',
        'range of cells']

    def __parseBytes (self):
        self.id = self.readUnsignedInt(1)
        self.rt = self.readUnsignedInt(1)
        flag = self.readUnsignedInt(2)
        self.unlinkedIFmt = (flag & 0x0001) != 0
        self.iFmt = self.readUnsignedInt(2)
        tokenBytes = self.readUnsignedInt(2)
        self.formulaBytes = self.readBytes(tokenBytes)

    def parseBytes (self):
        self.__parseBytes()
        self.appendLine("part type: %s"%globals.getValueOrUnknown(Brai.destTypes, self.id))
        self.appendLine("referenced data type: %s"%globals.getValueOrUnknown(Brai.linkTypes, self.rt))
        s = "number format: "
        if self.unlinkedIFmt:
            s += "custom format"
        else:
            s += "source data format"
            self.appendLine(s)

        self.appendLine("number format ID: %d"%self.iFmt)
        self.appendLine("formula size (bytes): %d"%len(self.formulaBytes))
        if len(self.formulaBytes) > 0:
            parser = formula.FormulaParser(self.header, self.formulaBytes)
            try:
                parser.parse()
                self.appendLine("formula: %s"%parser.getText())
            except formula.FormulaParserError as e:
                self.appendLine("formula parser error: %s"%e.args[0])

class MSODrawing(BaseRecordHandler):
    """Handler for the MSODRAWING record

This record consists of BIFF-like sub-records, with their own headers and 
contents.  The structure of this record is specified in [MS-ODRAW].pdf found 
somewhere in the MSDN website.  In case of multiple MSODRAWING records in a 
single worksheet stream, they need to be treated as if they are lumped 
together.
"""
    def __parseBytes (self):
        self.msodHdl = msodraw.MSODrawHandler(self.bytes, self)

    def parseBytes (self):
        self.__parseBytes()
        self.msodHdl.parseBytes()

    def fillModel (self, model):
        self.__parseBytes()
        self.msodHdl.fillModel(model)


class MSODrawingGroup(BaseRecordHandler):

    def __parseBytes (self):
        self.msodHdl = msodraw.MSODrawHandler(self.bytes, self)

    def parseBytes (self):
        self.__parseBytes()
        self.msodHdl.parseBytes()

    def fillModel (self, model):
        self.__parseBytes()
        self.msodHdl.fillModel(model)


class MSODrawingSelection(BaseRecordHandler):

    def __parseBytes (self):
        self.msodHdl = msodraw.MSODrawHandler(self.bytes, self)

    def parseBytes (self):
        self.__parseBytes()
        self.msodHdl.parseBytes()

    def fillModel (self, model):
        self.__parseBytes()
        self.msodHdl.fillModel(model)

